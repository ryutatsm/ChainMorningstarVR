"""Build a separate candidate for exactly the Glamur 2.5.1 ReShade DLL.

Requires pefile. Never edits the input. Does not load or execute the DLL.
The existing function, stack frame, image layout, calls and hook destinations
are retained. Only its 80-byte dispatch area and PE checksum are rewritten.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import pefile

ORIGINAL_SHA256 = 'da0f0736e80e73d6dcbc4400276df713c89b37c9dc6b7da0db3481898b7a177d'
START, END, RETURN = 0x1150CB, 0x11511B, 0x11512A
ORIGINAL = bytes.fromhex(
    '85c0745b8b44243883f80c720f4c8d0df1f9ffff41b805000000eb34'
    '83f809720f4c8d0dadf8ffff41b804000000eb20'
    '83f80875094c8d0dc9f6ffffeb0c83f807751c4c8d0d0bf5ffff41b806000000')
SUBMIT = {7: 0x114620, 8: 0x1147D0, 9: 0x1149A0, 12: 0x114AD0}


def dispatch_bytes():
    code = bytearray()
    labels = {'return': RETURN, 'install': END}
    fixups = []

    def emit(value): code.extend(bytes.fromhex(value))
    def label(name): labels[name] = START + len(code)
    def jump(opcode, name):
        emit(opcode + ' 00')
        fixups.append((len(code) - 1, name))
    def lea_r9(target):
        next_ip = START + len(code) + 7
        code.extend(b'\x4c\x8d\x0d' + struct.pack('<i', target - next_ip))

    emit('85 c0')                         # test eax,eax: sscanf result
    jump('74', 'return')
    emit('48 85 db')                      # NEW: test rbx,rbx: interface instance
    jump('74', 'return')
    emit('8b 44 24 38')                   # parsed interface version
    emit('41 b8 06 00 00 00')             # initialize all of r8d to slot 6
    emit('83 f8 0c')
    jump('72', 'below12')
    lea_r9(SUBMIT[12])
    emit('41 b0 05')                      # r8b=5, upper bits already zero
    jump('eb', 'install')
    label('below12')
    emit('83 f8 09')
    jump('72', 'below9')
    lea_r9(SUBMIT[9])
    emit('41 b0 04')
    jump('eb', 'install')
    label('below9')
    emit('83 f8 08')
    jump('75', 'below8')
    lea_r9(SUBMIT[8])
    jump('eb', 'install')
    label('below8')
    emit('83 f8 07')
    jump('75', 'return')
    lea_r9(SUBMIT[7])
    emit('90')                           # keep following code at original RVAs
    for offset, name in fixups:
        displacement = labels[name] - (START + offset + 1)
        assert -128 <= displacement <= 127
        code[offset] = displacement & 255
    assert len(code) == END - START == len(ORIGINAL) == 80
    return bytes(code)


def build(original: bytes):
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Unsupported original DLL')
    pe = pefile.PE(data=original)
    assert pe.FILE_HEADER.Machine == 0x8664 and pe.OPTIONAL_HEADER.Magic == 0x20B
    assert pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size == 0, 'Do not invalidate a signature'
    offset = pe.get_offset_from_rva(START)
    assert original[offset:offset + 80] == ORIGINAL
    containing = [entry.struct for entry in pe.DIRECTORY_ENTRY_EXCEPTION
                  if entry.struct.BeginAddress <= START < entry.struct.EndAddress]
    assert len(containing) == 1
    assert (containing[0].BeginAddress, containing[0].EndAddress) == (0x114FE0, 0x115138)
    for block in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
        assert all(not START <= entry.rva < END for entry in block.entries)
    patched = bytearray(original)
    patched[offset:offset + 80] = dispatch_bytes()
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum')
    checksum = pefile.PE(data=bytes(patched)).generate_checksum()
    struct.pack_into('<I', patched, checksum_offset, checksum)
    differences = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    assert len(patched) == len(original)
    assert all(offset <= i < offset + 80 or checksum_offset <= i < checksum_offset + 4
               for i in differences)
    out_pe = pefile.PE(data=bytes(patched))
    assert out_pe.verify_checksum()
    assert out_pe.OPTIONAL_HEADER.SizeOfImage == pe.OPTIONAL_HEADER.SizeOfImage
    return bytes(patched), {
        'original_sha256': ORIGINAL_SHA256,
        'candidate_sha256': hashlib.sha256(patched).hexdigest(),
        'file_size_unchanged': len(original),
        'dispatch_rva': hex(START), 'dispatch_file_offset': hex(offset), 'dispatch_bytes': 80,
        'checksum_file_offset': hex(checksum_offset),
        'changed_byte_count': len(differences),
        'all_other_bytes_identical': True,
        'original_dispatch_hex': ORIGINAL.hex(), 'candidate_dispatch_hex': dispatch_bytes().hex(),
        'pe_checksum_valid': True,
        'signature_present_in_original': False,
        'game_tested': False,
        'scope': 'Binary guard for one SHA256-pinned DLL; not a source rebuild or a general ReShade update',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.original.resolve() == args.output.resolve():
        raise ValueError('Never patch in place')
    result, evidence = build(args.original.read_bytes())
    if args.output.exists():
        raise FileExistsError('Preserve existing output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    args.output.with_suffix('.verification.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))
