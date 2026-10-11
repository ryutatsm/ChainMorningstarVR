"""Inspect an existing AMD64 minidump, without attaching to or launching a game.

Uses documented MINIDUMP streams and x64 CONTEXT. Reads only selected pointer
fields; missing memory is reported as unavailable, never as a null pointer.
No stack unwinding, allocation-lifetime proof, write history, or mod attribution.
Output may contain process addresses; keep it local along with the input dump.
"""
from __future__ import annotations

import argparse
import bisect
import json
import mmap
from pathlib import Path, PureWindowsPath
import struct

ENGINE_TIMESTAMP = 0x5AEADAA0
ENGINE_IMAGE_SIZE = 0x3959000
FAULT_BYTES = {0x14339F: bytes.fromhex('3907'), 0x534D71: bytes.fromhex('f30f11406c')}
REG_NAMES = ('rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi',
             'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15', 'rip')


class DumpFormatError(ValueError):
    pass


class Dump:
    def __init__(self, data):
        self.data = data
        self.streams = {}
        self.ranges = []
        self.modules = []
        if self.at(0, 4) != b'MDMP' or self.unpack('<I', 4)[0] & 0xFFFF != 0xA793:
            raise DumpFormatError('Not a supported MINIDUMP header')
        self.at(0, 32)
        count, directory = self.unpack('<II', 8)
        self.at(directory, count * 12)
        for i in range(count):
            kind, size, rva = self.unpack('<III', directory + i * 12)
            self.at(rva, size)
            if kind in self.streams and kind != 0:
                raise DumpFormatError(f'Duplicate stream type {kind}')
            self.streams[kind] = (rva, size)
        if 9 in self.streams:  # Memory64ListStream, contiguous file payload
            start, size = self.streams[9]
            if size < 16:
                raise DumpFormatError('Short Memory64List')
            count, file_offset = self.unpack('<QQ', start)
            self.check_table(count, 16, size - 16)
            for i in range(count):
                address, length = self.unpack('<QQ', start + 16 + i * 16)
                self.add_range(address, length, file_offset)
                file_offset += length
        elif 5 in self.streams:  # MemoryListStream, individual file payload RVAs
            start, size = self.streams[5]
            if size < 4:
                raise DumpFormatError('Short MemoryList')
            count = self.unpack('<I', start)[0]
            self.check_table(count, 16, size - 4)
            for i in range(count):
                address, length, rva = self.unpack('<QII', start + 4 + i * 16)
                self.add_range(address, length, rva)
        self.ranges.sort()
        for left, right in zip(self.ranges, self.ranges[1:]):
            if left[1] > right[0]:
                raise DumpFormatError('Overlapping memory descriptors')
        self.starts = [entry[0] for entry in self.ranges]
        if 4 in self.streams:
            start, size = self.streams[4]
            if size < 4:
                raise DumpFormatError('Short ModuleList')
            count = self.unpack('<I', start)[0]
            self.check_table(count, 108, size - 4)
            for i in range(count):
                base, length, checksum, stamp, name_rva = self.unpack('<QIIII', start + 4 + i * 108)
                name_size = self.unpack('<I', name_rva)[0]
                if name_size % 2 or name_size > 65536:
                    raise DumpFormatError('Invalid module name length')
                try:
                    name = self.at(name_rva + 4, name_size).decode('utf-16-le')
                except UnicodeError as error:
                    raise DumpFormatError('Invalid module name') from error
                self.modules.append({'name': PureWindowsPath(name).name,
                                     'base': base, 'size': length, 'timestamp': stamp})

    def at(self, offset, size):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise DumpFormatError('Truncated or out-of-bounds dump data')
        return self.data[offset:offset + size]

    def unpack(self, fmt, offset):
        return struct.unpack(fmt, self.at(offset, struct.calcsize(fmt)))

    @staticmethod
    def check_table(count, stride, available):
        if count > available // stride:
            raise DumpFormatError('Descriptor count exceeds stream bounds')

    def add_range(self, address, length, offset):
        # Validate using lengths without copying full-memory payloads.
        if offset > len(self.data) or length > len(self.data) - offset or address + length > 1 << 64:
            raise DumpFormatError('Memory range exceeds file or address space')
        if length:
            self.ranges.append((address, address + length, offset))

    def memory(self, address, size):
        if size < 0 or size > 4096:
            raise ValueError('Only bounded small probes are supported')
        result = bytearray()
        while len(result) < size:
            pos = address + len(result)
            index = bisect.bisect_right(self.starts, pos) - 1
            if index < 0:
                return None
            start, end, offset = self.ranges[index]
            if pos >= end:
                return None
            amount = min(size - len(result), end - pos)
            result.extend(self.at(offset + pos - start, amount))
        return bytes(result)

    def pointer(self, address):
        data = self.memory(address, 8)
        return None if data is None else struct.unpack('<Q', data)[0]

    def probe(self, address, expected=None):
        value = self.pointer(address)
        row = {'address': hex(address), 'captured': value is not None,
               'value': None if value is None else hex(value)}
        if expected is not None:
            row['matches_expected'] = None if value is None else value == expected
        return row

    def exception(self):
        if 6 not in self.streams:
            return None
        start, size = self.streams[6]
        if size < 168:
            raise DumpFormatError('Short ExceptionStream')
        tid = self.unpack('<I', start)[0]
        code, flags = self.unpack('<II', start + 8)
        address = self.unpack('<Q', start + 24)[0]
        count = self.unpack('<I', start + 32)[0]
        if count > 15:
            raise DumpFormatError('Invalid exception parameter count')
        params = list(self.unpack('<' + 'Q' * count, start + 40))
        ctx_size, ctx_rva = self.unpack('<II', start + 160)
        self.at(ctx_rva, ctx_size)
        registers = None
        architecture = None
        if 7 in self.streams:
            srva, ssize = self.streams[7]
            if ssize >= 2:
                architecture = self.unpack('<H', srva)[0]
        if architecture == 9 and ctx_size >= 256:
            ctx_flags = self.unpack('<I', ctx_rva + 48)[0]
            if ctx_flags & 0x00100003 == 0x00100003:
                registers = dict(zip(REG_NAMES, self.unpack('<17Q', ctx_rva + 120)))
        return {'thread_id': tid, 'code': code, 'flags': flags, 'address': address,
                'parameters': params, 'registers': registers, 'architecture': architecture}


def inspect_dump(dump):
    result = {'schema': 'cms-saved-minidump-probes-v1', 'read_only': True,
              'game_launched': False, 'process_attached': False,
              'root_cause_mod_identified': False,
              'limits': ['No allocation lifetime proof or past write history',
                         'Missing memory is unavailable, not zero',
                         'Image metadata and byte checks do not authenticate the entire loaded executable'],
              'memory_ranges': len(dump.ranges), 'engine_probes': None}
    exception = dump.exception()
    if exception is None:
        result['status'] = 'no_exception_stream'
        return result
    regs = exception.pop('registers')
    result['exception'] = {**exception, 'address': hex(exception['address']),
                           'code': hex(exception['code']), 'parameters': [hex(x) for x in exception['parameters']]}
    result['registers'] = None if regs is None else {k: hex(v) for k, v in regs.items()}
    module = next((m for m in dump.modules if m['base'] <= exception['address'] < m['base'] + m['size']), None)
    result['fault_module'] = None if module is None else module['name']
    rva = None if module is None else exception['address'] - module['base']
    result['fault_rva'] = None if rva is None else hex(rva)
    result['status'] = 'unsupported_or_insufficient_context'
    if (regs is None or module is None or module['name'].lower() != 'skyrimvr.exe'
            or module['timestamp'] != ENGINE_TIMESTAMP or module['size'] != ENGINE_IMAGE_SIZE
            or exception['code'] != 0xC0000005 or regs['rip'] != exception['address'] or rva not in FAULT_BYTES):
        return result
    actual = dump.memory(exception['address'], len(FAULT_BYTES[rva]))
    result['fault_instruction_matches'] = None if actual is None else actual == FAULT_BYTES[rva]
    if actual != FAULT_BYTES[rva]:
        result['status'] = 'instruction_unavailable_or_changed'
        return result
    base = module['base']
    if rva == 0x534D71:
        scene = regs['rbx']
        if scene < 0x68:
            return result
        owner = scene - 0x68
        probes = {
            'kind': 'mist_menu_candidate_fields', 'owner_address': hex(owner), 'scene_address': hex(scene),
            'owner_vtable': dump.probe(owner, base + 0x173DB68),
            'scene_vtable': dump.probe(scene, base + 0x16AA518),
            'node_field': dump.probe(scene + 0x20, regs['rax']),
            'other_scene_node_fields': [dump.probe(scene + offset) for offset in (0x18, 0x28, 0x30, 0x38)],
            'saved_owner_on_known_frame': dump.probe(regs['rsp'] + 0xE8, owner),
            'postdisplay_return_on_known_frame': dump.probe(regs['rsp'] + 0xD8, base + 0x8DA726),
            'owner_identity_proven': False,
        }
    else:
        probes = {'kind': 'actor_scene_global_at_exception',
                  'scene_global': dump.probe(base + 0x3423080),
                  'fault_lock_value': hex(regs['rdi']),
                  'r13_actor_candidate_vtable': dump.probe(regs['r13']),
                  'shutdown_path_proven_by_this_tool': False}
    result['engine_probes'] = probes
    result['status'] = 'candidate_fields_read'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.suffix.lower() != '.json' or args.output.resolve() == args.dump.resolve():
        parser.error('Output must be a separate JSON file')
    try:
        with args.dump.open('rb') as source:
            before = args.dump.stat()
            if before.st_size < 32:
                raise DumpFormatError('Dump file is empty or incomplete')
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as memory:
                result = inspect_dump(Dump(memory))
            after = args.dump.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise DumpFormatError('Input is still changing; wait until capture has finished')
        result['input_file'] = args.dump.name
        result['input_bytes'] = before.st_size
        # Do not overwrite earlier evidence, the source dump, or symlink targets.
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write('\n')
        print(json.dumps({'status': result['status'], 'fault_module': result.get('fault_module'),
                          'fault_rva': result.get('fault_rva')}))
    except (OSError, DumpFormatError) as error:
        parser.exit(2, f'Unable to inspect dump: {error}\n')


if __name__ == '__main__':
    main()
