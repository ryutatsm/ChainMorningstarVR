"""Emulate the actual original/patched x64 function without loading the DLL.

External logging, resolver, sscanf and hook installation are mocked. The real
function instructions, stack handling, dispatch and null dereference execute
inside Unicorn. This is not an OpenVR, rendering or Skyrim integration test.
Requires pefile, capstone and unicorn 2.1.4.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.x86_const import *
from patch_installed_build import build, START, END, SUBMIT

ENTRY, FUNCTION_END = 0x114FE0, 0x115138
DATA, STACK, EXTERNAL = 0x50000000, 0x70000000, 0x60000000
RESOLVER, SENTINEL = EXTERNAL + 0x1000, EXTERNAL + 0x2000
SP = STACK + 0x8008
OBJECT, VTABLE, ERROR = DATA + 0x1000, DATA + 0x2000, DATA + 0x800
NONVOLATILE = [UC_X86_REG_RBX, UC_X86_REG_RBP, UC_X86_REG_RSI, UC_X86_REG_RDI,
               UC_X86_REG_R12, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_R15]
VOLATILE = [UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9,
            UC_X86_REG_R10, UC_X86_REG_R11]
LOG_HELPERS = {0x2EA00, 0x1E080, 0x27980, 0x36BD0, 0x2ECB0}


class FunctionHarness:
    def __init__(self, dll, base):
        self.base = base
        self.pe = pefile.PE(data=dll)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_64)
        self.mu.mem_map(base, (self.pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        self.mu.mem_write(base, self.pe.get_memory_mapped_image())
        for address in (DATA, STACK, EXTERNAL):
            self.mu.mem_map(address, 0x10000)
        self.mu.mem_write(OBJECT, struct.pack('<Q', VTABLE))
        self.mu.hook_add(UC_HOOK_CODE, self.step)
        self.mu.hook_add(UC_HOOK_MEM_INVALID, self.invalid)

    def string(self, address):
        out = bytearray()
        for i in range(256):
            byte = self.mu.mem_read(address + i, 1)[0]
            if byte == 0:
                return out.decode('ascii')
            out.append(byte)
        raise AssertionError('Unterminated string')

    def return_call(self, result):
        mu = self.mu
        # Expose accidental reliance on volatile registers across real calls.
        for index, register in enumerate(VOLATILE):
            mu.reg_write(register, 0xFEED000000000000 + index)
        mu.reg_write(UC_X86_REG_RAX, result & 0xFFFFFFFFFFFFFFFF)
        sp = mu.reg_read(UC_X86_REG_RSP)
        destination, = struct.unpack('<Q', mu.mem_read(sp, 8))
        mu.reg_write(UC_X86_REG_RSP, sp + 8)
        mu.reg_write(UC_X86_REG_RIP, destination)

    def step(self, mu, address, size, _):
        rva = address - self.base
        if rva in LOG_HELPERS:
            self.return_call(0)
        elif rva == 0x35590:  # resolve original function pointer
            assert mu.reg_read(UC_X86_REG_RCX) == self.base + ENTRY
            self.return_call(RESOLVER)
        elif address == RESOLVER:
            self.resolve_count += 1
            assert self.string(mu.reg_read(UC_X86_REG_RCX)) == self.name
            assert mu.reg_read(UC_X86_REG_RDX) == (ERROR if self.error_pointer else 0)
            if self.error_pointer:
                mu.mem_write(ERROR, struct.pack('<I', 0 if self.instance else 109))
            self.return_call(self.instance)
        elif rva == 0x10D960:  # sscanf, using explicit test values
            assert self.string(mu.reg_read(UC_X86_REG_RCX)) == self.name
            assert self.string(mu.reg_read(UC_X86_REG_RDX)) == 'IVRCompositor_%u'
            if self.scan_result == 1:
                mu.mem_write(mu.reg_read(UC_X86_REG_R8), struct.pack('<I', self.version))
            self.return_call(self.scan_result)
        elif rva == 0x34F20:  # hook installer, record arguments without installing anything
            assert self.string(mu.reg_read(UC_X86_REG_RCX)) == 'IVRCompositor::Submit'
            self.installs.append((mu.reg_read(UC_X86_REG_RDX), mu.reg_read(UC_X86_REG_R8),
                                  mu.reg_read(UC_X86_REG_R9) - self.base))
            self.return_call(0xDEADBEEF)

    def invalid(self, mu, access, address, size, value, _):
        self.invalid_reads.append({'instruction_rva': hex(mu.reg_read(UC_X86_REG_RIP) - self.base),
                                   'address': address, 'size': size})
        return False

    def run(self, name, version, scan_result, instance, error_pointer=True):
        self.name, self.version, self.scan_result = name, version, scan_result
        self.instance, self.error_pointer = instance, error_pointer
        self.installs, self.invalid_reads, self.resolve_count = [], [], 0
        mu = self.mu
        mu.mem_write(DATA, name.encode() + b'\0')
        mu.mem_write(ERROR, struct.pack('<I', 0xCAFE))
        mu.mem_write(SP - 0x100, b'\xCC' * 0x300)
        mu.mem_write(SP, struct.pack('<Q', SENTINEL))
        saved = {register: 0xABCD0000 + index for index, register in enumerate(NONVOLATILE)}
        for register, value in saved.items(): mu.reg_write(register, value)
        for register in VOLATILE: mu.reg_write(register, 0xFEEDFFFFFFFFFFFF)
        mu.reg_write(UC_X86_REG_RAX, 0xBAD0)
        mu.reg_write(UC_X86_REG_RCX, DATA)
        mu.reg_write(UC_X86_REG_RDX, ERROR if error_pointer else 0)
        mu.reg_write(UC_X86_REG_RSP, SP)
        mu.reg_write(UC_X86_REG_EFLAGS, 0x202)
        failure = None
        try:
            mu.emu_start(self.base + ENTRY, SENTINEL, count=500)
        except UcError as error:
            failure = str(error)
        assert self.resolve_count == 1
        expected_error = (0 if instance else 109) if error_pointer else 0xCAFE
        assert struct.unpack('<I', mu.mem_read(ERROR, 4))[0] == expected_error
        if failure:
            assert self.invalid_reads == [{'instruction_rva': '0x11511b', 'address': 0, 'size': 8}]
            assert not self.installs and instance == 0
            return {'fault': True, 'invalid': self.invalid_reads}
        assert mu.reg_read(UC_X86_REG_RIP) == SENTINEL, 'Instruction limit reached'
        assert mu.reg_read(UC_X86_REG_RSP) == SP + 8
        assert mu.reg_read(UC_X86_REG_RAX) == instance
        assert all(mu.reg_read(register) == value for register, value in saved.items())
        return {'fault': False, 'return': instance, 'installs': self.installs,
                'error': expected_error, 'nonvolatile_registers_and_stack_preserved': True}


def verify(original):
    candidate, evidence = build(original)
    versions = list(range(33)) + [255, 256, 65535, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
    cases = [(f'IVRCompositor_{v:03d}', v, 1, True) for v in versions]
    cases += [('IVRSystem_019', 0, 0, True), ('garbage', 0, 0, True),
              ('', 0, -1, True), ('IVRCompositor_', 0, -1, True),
              ('IVRCompositor_022', 22, 1, False)]
    bases = [0x10000000, 0x180000000, 0x7FFA00000000]
    equivalent = prevented = patched_passed = 0
    for base in bases:
        old, new = FunctionHarness(original, base), FunctionHarness(candidate, base)
        for name, version, scan, error_pointer in cases:
            for instance in (0, OBJECT):
                before = old.run(name, version, scan, instance, error_pointer)
                after = new.run(name, version, scan, instance, error_pointer)
                assert not after['fault'], (name, base, instance)
                expected = []
                if instance and scan == 1 and version >= 7:
                    key, slot = (12, 5) if version >= 12 else ((9, 4) if version >= 9 else (version, 6))
                    expected = [(VTABLE, slot, SUBMIT[key])]
                assert after['installs'] == expected, (name, after)
                patched_passed += 1
                if before['fault']:
                    assert not instance and scan == 1 and version >= 7
                    prevented += 1
                else:
                    assert before == after, (name, before, after)
                    equivalent += 1
    # SHA pin must refuse an unrelated or modified binary; do not patch arbitrary builds.
    invalid = bytearray(original)
    invalid[-1] ^= 1
    rejected = False
    try: build(bytes(invalid))
    except ValueError: rejected = True
    assert rejected
    evidence.update({'emulator': 'Unicorn 2.1.4 x86-64', 'image_bases': [hex(x) for x in bases],
        'paired_scenarios': patched_passed, 'original_null_faults_reproduced_and_prevented': prevented,
        'nonfault_original_results_preserved': equivalent, 'wrong_input_hash_rejected': True,
        'external_functions_mocked': ['logging', 'hook lookup', 'VR_GetGenericInterface', 'sscanf', 'hook install'],
        'game_or_original_dll_loaded': False, 'rendering_integration_tested': False})
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    pe = pefile.PE(data=candidate)
    evidence['candidate_dispatch_disassembly'] = [f'{ins.address:08x}: {ins.mnemonic} {ins.op_str}'
        for ins in md.disasm(pe.get_data(START, END - START), START)]
    return candidate, evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    original = args.original.read_bytes()
    candidate, evidence = verify(original)
    assert args.original.read_bytes() == original
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / 'dxgi.dll'
    assert output.resolve() != args.original.resolve()
    assert not output.exists() or output.read_bytes() == candidate
    output.write_bytes(candidate)
    (args.output_dir / 'BINARY_GUARD_VERIFICATION.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: evidence[k] for k in ('candidate_sha256', 'changed_byte_count', 'paired_scenarios',
        'original_null_faults_reproduced_and_prevented', 'nonfault_original_results_preserved',
        'wrong_input_hash_rejected', 'game_or_original_dll_loaded')}, indent=2))
