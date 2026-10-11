"""Synthetic documented-format dumps; no game or private memory used."""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from inspect_saved_minidump import Dump, DumpFormatError, inspect_dump

BASE = 0x7FF610000000
OWNER = 0x1E000050000
STACK = 0xC400001000


def fixture(*, fault=0x534D71, format64=True, include_owner=True, node=0x14,
            timestamp=0x5AEADAA0, instruction=None, arch=9, context_flags=0x100003,
            owner_vtable=None, extra_ranges=()):
    data = bytearray(32 + 5 * 12)
    streams = []

    def append(blob):
        while len(data) % 4:
            data.append(0)
        start = len(data)
        data.extend(blob)
        return start

    def stream(kind, blob):
        streams.append((kind, len(blob), append(blob)))

    name = 'C:\\Private\\Game\\SkyrimVR.exe'.encode('utf-16-le')
    name_rva = append(struct.pack('<I', len(name)) + name)
    module = bytearray(108)
    struct.pack_into('<QIIII', module, 0, BASE, 0x3959000, 0, timestamp, name_rva)
    stream(4, struct.pack('<I', 1) + module)
    system = bytearray(56)
    struct.pack_into('<H', system, 0, arch)
    stream(7, system)
    context = bytearray(256)
    struct.pack_into('<I', context, 48, context_flags)
    regs = [0x14, 0, 0, OWNER + 0x68, STACK, 0, 0, 0x220] + [0] * 8 + [BASE + fault]
    struct.pack_into('<17Q', context, 120, *regs)
    context_rva = append(context)
    exception = bytearray(168)
    struct.pack_into('<I', exception, 0, 42)
    struct.pack_into('<I', exception, 8, 0xC0000005)
    struct.pack_into('<Q', exception, 24, BASE + fault)
    struct.pack_into('<I', exception, 32, 2)
    struct.pack_into('<QQ', exception, 40, 1 if fault == 0x534D71 else 0, 0x80 if fault == 0x534D71 else 0x220)
    struct.pack_into('<II', exception, 160, len(context), context_rva)
    stream(6, exception)
    owner = bytearray(0xB0)
    struct.pack_into('<Q', owner, 0, BASE + 0x173DB68 if owner_vtable is None else owner_vtable)
    struct.pack_into('<Q', owner, 0x68, BASE + 0x16AA518)
    struct.pack_into('<Q', owner, 0x88, node)
    stack = bytearray(0x100)
    struct.pack_into('<Q', stack, 0xD8, BASE + 0x8DA726)
    struct.pack_into('<Q', stack, 0xE8, OWNER)
    default_instruction = bytes.fromhex('f30f11406c' if fault == 0x534D71 else '3907')
    ranges = [(BASE + fault, default_instruction if instruction is None else instruction),
              (BASE + 0x3423080, bytes(8)), (STACK, stack)]
    if include_owner:
        ranges.append((OWNER, owner))
    ranges.extend(extra_ranges)
    if format64:
        descriptors = struct.pack('<QQ', len(ranges), 0) + b''.join(struct.pack('<QQ', a, len(b)) for a, b in ranges)
        descriptor_rva = append(descriptors)
        payload_rva = append(b''.join(b for a, b in ranges))
        struct.pack_into('<Q', data, descriptor_rva + 8, payload_rva)
        streams.append((9, len(descriptors), descriptor_rva))
    else:
        entries = [(a, len(b), append(b)) for a, b in ranges]
        stream(5, struct.pack('<I', len(entries)) + b''.join(struct.pack('<QII', *x) for x in entries))
    struct.pack_into('<4sIIIIIQ', data, 0, b'MDMP', 0xA793, len(streams), 32, 0, 0, 2 if format64 else 0)
    for i, row in enumerate(streams):
        struct.pack_into('<III', data, 32 + i * 12, *row)
    return bytes(data)


class MinidumpTests(unittest.TestCase):
    def test_memory64_reads_render_fields_and_saved_frame(self):
        report = inspect_dump(Dump(fixture()))
        self.assertEqual(report['status'], 'candidate_fields_read')
        fields = report['engine_probes']
        self.assertTrue(fields['owner_vtable']['matches_expected'])
        self.assertTrue(fields['node_field']['matches_expected'])
        self.assertTrue(fields['saved_owner_on_known_frame']['matches_expected'])
        self.assertEqual(fields['node_field']['value'], '0x14')
        self.assertFalse(fields['owner_identity_proven'])

    def test_memory32_descriptor_also_uses_64_bit_process_addresses(self):
        report = inspect_dump(Dump(fixture(format64=False)))
        self.assertEqual(report['engine_probes']['owner_address'], hex(OWNER))

    def test_absent_memory_is_not_a_null_pointer(self):
        field = inspect_dump(Dump(fixture(include_owner=False)))['engine_probes']['node_field']
        self.assertFalse(field['captured'])
        self.assertIsNone(field['value'])
        self.assertIsNone(field['matches_expected'])

    def test_captured_zero_is_distinct_from_absent(self):
        field = inspect_dump(Dump(fixture(fault=0x14339F)))['engine_probes']['scene_global']
        self.assertTrue(field['captured'])
        self.assertEqual(field['value'], '0x0')

    def test_mismatched_owner_vtable_remains_a_candidate(self):
        fields = inspect_dump(Dump(fixture(owner_vtable=0x72656E)))['engine_probes']
        self.assertFalse(fields['owner_vtable']['matches_expected'])
        self.assertFalse(fields['owner_identity_proven'])

    def test_changed_node_field_is_not_silently_equated_with_register(self):
        field = inspect_dump(Dump(fixture(node=0x100000)))['engine_probes']['node_field']
        self.assertFalse(field['matches_expected'])

    def test_wrong_image_metadata_or_architecture_stops_probes(self):
        for args in ({'timestamp': 0}, {'arch': 12}, {'context_flags': 0x100001}):
            with self.subTest(args=args):
                self.assertIsNone(inspect_dump(Dump(fixture(**args)))['engine_probes'])

    def test_changed_fault_instruction_stops_layout_interpretation(self):
        report = inspect_dump(Dump(fixture(instruction=b'\x90' * 5)))
        self.assertEqual(report['status'], 'instruction_unavailable_or_changed')
        self.assertIsNone(report['engine_probes'])

    def test_short_file_and_excess_descriptor_counts_fail(self):
        for data in (fixture()[:-1], b'MDMP', fixture()[:32]):
            with self.subTest(size=len(data)), self.assertRaises(DumpFormatError):
                Dump(data)
        data = bytearray(fixture())
        start, size = Dump(data).streams[9]
        struct.pack_into('<Q', data, start, 1 << 60)
        with self.assertRaises(DumpFormatError):
            Dump(data)

    def test_contiguous_ranges_can_supply_one_pointer(self):
        dump = Dump(fixture(extra_ranges=[(0x5000, b'\x88\x77\x66\x55'), (0x5004, b'\x44\x33\x22\x11')]))
        self.assertEqual(dump.pointer(0x5000), 0x1122334455667788)
        self.assertIsNone(dump.pointer(0x5001))

    def test_gaps_and_overlaps_are_not_fabricated_data(self):
        dump = Dump(fixture(extra_ranges=[(0x5000, b'1234'), (0x5005, b'5678')]))
        self.assertIsNone(dump.pointer(0x5000))
        with self.assertRaises(DumpFormatError):
            Dump(fixture(extra_ranges=[(0x5000, b'1234'), (0x5002, b'5678')]))

    def test_report_does_not_expose_module_install_path(self):
        self.assertEqual(inspect_dump(Dump(fixture()))['fault_module'], 'SkyrimVR.exe')

    def test_cli_leaves_dump_unchanged_and_refuses_existing_output(self):
        script = Path(__file__).with_name('inspect_saved_minidump.py')
        temp_root = script.parent.resolve()
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            self.assertEqual(Path(temp).resolve().parent, temp_root)
            source, output = Path(temp)/'synthetic.dmp', Path(temp)/'result.json'
            source.write_bytes(fixture())
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            command = [sys.executable, str(script), str(source), '--output', str(output)]
            run = subprocess.run(command, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            first = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
