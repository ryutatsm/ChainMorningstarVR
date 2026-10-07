"""Binary regression tests; fixtures are synthetic and contain no game bytes."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import zlib

path = Path(__file__).resolve().parents[1] / "Source/xEdit/build_plugin.py"
spec = importlib.util.spec_from_file_location("cms_build_plugin", path)
cms = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cms
spec.loader.exec_module(cms)


def synthetic_source():
    weapon = cms.Record(b"WEAP", 0, 0x13988, 44, (
        (b"EDID", b"SteelMace\0"), (b"OBND", bytes(12)), (b"FULL", b"\xed\xc0\0\0"),
        (b"MODL", b"Weapons\\Steel\\SteelMace.nif\0"), (b"MODT", b"stale hashes"),
        (b"MODS", b"stale texture swaps"), (b"ETYP", struct.pack("<I", 0x1234)),
        (b"BIDS", struct.pack("<I", 0x2234)), (b"BAMT", struct.pack("<I", 0x3234)),
        (b"KSIZ", struct.pack("<I", 1)), (b"KWDA", struct.pack("<I", 0x8F958)),
        (b"DESC", bytes(4)), (b"INAM", struct.pack("<I", 0x4234)),
        (b"WNAM", struct.pack("<I", 0x14305)), (b"TNAM", struct.pack("<I", 0x5234)),
        (b"NAM9", struct.pack("<I", 0x6234)), (b"NAM8", struct.pack("<I", 0x7234)),
        (b"DATA", struct.pack("<IfH", 65, 14.0, 10)),
        (b"DNAM", b"\x04" + bytes(99)), (b"CRDT", bytes(24)), (b"VNAM", bytes(4))))
    chest = cms.Record(b"CONT", 0, 0x10FDE6, 44, (
        (b"EDID", b"MerchantWhiterunEorlundChest\0"), (b"DATA", b"\x02" + bytes(4))))
    return weapon, chest


def inspect_binary(raw):
    """Independent reader: checks container boundaries and serialized subrecords."""
    found = {}
    groups = []
    at = 0
    ends = []
    while at < len(raw):
        while ends and at == ends[-1]:
            ends.pop()
        if at + 24 > len(raw):
            raise AssertionError("truncated header")
        tag = raw[at:at + 4]
        size = int.from_bytes(raw[at + 4:at + 8], "little")
        end = at + size if tag == b"GRUP" else at + 24 + size
        if end > (ends[-1] if ends else len(raw)):
            raise AssertionError("record extends outside its group")
        if tag == b"GRUP":
            if size < 24:
                raise AssertionError("invalid group size")
            groups.append(raw[at + 8:at + 12])
            ends.append(end)
            at += 24
            continue
        form_id = int.from_bytes(raw[at + 12:at + 16], "little")
        if int.from_bytes(raw[at + 8:at + 12], "little") != 0:
            raise AssertionError("unexpected record flags")
        if int.from_bytes(raw[at + 20:at + 22], "little") != 44:
            raise AssertionError("unexpected form version")
        fields = {}
        pos = at + 24
        while pos < end:
            sig = raw[pos:pos + 4]
            n = int.from_bytes(raw[pos + 4:pos + 6], "little")
            if pos + 6 + n > end or sig in fields:
                raise AssertionError("bad subrecord boundary/duplicate")
            fields[sig] = raw[pos + 6:pos + 6 + n]
            pos += 6 + n
        found[(tag, form_id)] = fields
        at = end
    return found, groups


class PluginBinaryTests(unittest.TestCase):
    def test_original_audio_descriptors_keep_weapon_ids_and_spatial_template(self):
        weapon, chest = synthetic_source()
        template = cms.Record(b'SNDR',0,0x3D128,40,(
            (b'EDID', b'PHYChainSD\0'), (b'CNAM', bytes([10,84,239,30])),
            (b'GNAM', struct.pack('<I',0x1234)), (b'ONAM', struct.pack('<I',0x5678)),
            (b'ANAM',b'old1.wav\0'), (b'ANAM',b'old2.wav\0'),
            (b'LNAM', bytes([1,0,0,0])), (b'BNAM',bytes(6))))
        records, groups = inspect_binary(cms.build_plugin(weapon,chest,(-1,-1,-1,1,1,1),template))
        self.assertEqual(groups,[b'STAT',b'WEAP',b'SNDR'])
        self.assertEqual(struct.unpack('<fII',records[(b'TES4',0)][b'HEDR'])[1:],(8,0x805))
        self.assertEqual(records[(b'WEAP',0x1000800)][b'WNAM'],struct.pack('<I',0x1000801))
        # User-requested audible separation depends on the ESP, not merely the
        # DLL gate: only scrape may loop. Keep this independent of AUDIO_RECORDS.
        self.assertEqual(records[(b'SNDR',0x1000802)][b'LNAM'][1] & 0x38,8)
        self.assertEqual(records[(b'SNDR',0x1000803)][b'LNAM'][1] & 0x38,0)
        self.assertEqual(records[(b'SNDR',0x1000804)][b'LNAM'][1] & 0x38,0)
        for ident, name, filename, loop in cms.AUDIO_RECORDS:
            record = records[(b'SNDR',ident)]
            self.assertEqual(record[b'ANAM'],('fx\\ChainMorningstarVR\\'+filename+'\0').encode())
            self.assertEqual(record[b'EDID'],name.encode()+b'\0')
            self.assertEqual(record[b'LNAM'][1],8 if loop else 0)
            self.assertEqual(record[b'ONAM'],template.field(b'ONAM'))
            self.assertEqual(record[b'GNAM'],template.field(b'GNAM'))
            self.assertEqual(record[b'BNAM'],bytes([0,0,128,0,0,0]))
        conditional = cms.Record(template.signature,0,template.form_id,40,template.fields+((b'CTDA',bytes(32)),))
        with self.assertRaises(ValueError): cms.build_audio_records(conditional)

    def test_output_formids_models_native_fields_and_no_overrides(self):
        weapon, chest = synthetic_source()
        raw = cms.build_plugin(weapon, chest, (-30, -20, -60, 30, 160, 60))
        records, groups = inspect_binary(raw)
        self.assertEqual(groups, [b"STAT", b"WEAP"])
        self.assertEqual(set(records), {(b"TES4", 0), (b"STAT", 0x1000801), (b"WEAP", 0x1000800)})
        header = records[(b"TES4", 0)]
        self.assertEqual(header[b"MAST"], b"Skyrim.esm\0")
        self.assertEqual(struct.unpack("<fII", header[b"HEDR"])[1:], (4, 0x802))
        dst = records[(b"WEAP", 0x1000800)]
        stat = records[(b"STAT", 0x1000801)]
        self.assertEqual(dst[b"WNAM"], struct.pack("<I", 0x1000801))
        self.assertEqual(dst[b"MODL"], stat[b"MODL"])
        self.assertEqual(dst[b"MODL"], b"weapons\\ChainMorningstarVR\\ChainMorningstar.nif\0")
        self.assertEqual(dst[b"FULL"].decode("utf-8"), "チェーンドモーニングスター\0")
        self.assertEqual(struct.unpack("<IfH", dst[b"DATA"]), (550, 17.0, 44))
        self.assertEqual(dst[b"DNAM"][0], 4)
        self.assertEqual(stat[b"DNAM"], struct.pack("<fIB3x", 90, 0, 0))
        self.assertFalse({b"DESC", b"MODT", b"MODS"} & dst.keys())
        for tag in [b"ETYP", b"BIDS", b"BAMT", b"KWDA", b"INAM", b"TNAM", b"NAM9", b"NAM8", b"DNAM", b"CRDT"]:
            self.assertEqual(dst[tag], weapon.field(tag), tag)
        self.assertEqual(raw, cms.build_plugin(weapon, chest, (-30, -20, -60, 30, 160, 60)))

    def test_mismatched_source_and_nonrespawning_chest_are_rejected(self):
        weapon, chest = synthetic_source()
        bad_weapon = cms.Record(weapon.signature, 0, 0x800, 44, weapon.fields)
        with self.assertRaises(ValueError):
            cms.build_plugin(bad_weapon, chest, (-1, -1, -1, 1, 1, 1))
        bad_chest = cms.Record(chest.signature, 0, chest.form_id, 44,
                               ((b"EDID", chest.field(b"EDID")), (b"DATA", bytes(5))))
        with self.assertRaises(ValueError):
            cms.build_plugin(weapon, bad_chest, (-1, -1, -1, 1, 1, 1))
        scripted = cms.Record(weapon.signature, 0, weapon.form_id, 44, weapon.fields + ((b"VMAD", b"script"),))
        with self.assertRaises(ValueError):
            cms.build_plugin(scripted, chest, (-1, -1, -1, 1, 1, 1))

    def test_parser_compression_and_truncated_data(self):
        raw = cms.encode_record(b"WEAP", 0x13988, list(synthetic_source()[0].fields))
        expected = cms.parse_record(raw)
        body = struct.pack("<I", len(raw) - 24) + zlib.compress(raw[24:])
        zipped = cms.HEADER.pack(b"WEAP", len(body), 0x40000, 0x13988, 0, 44, 0) + body
        self.assertEqual(cms.parse_record(zipped).fields, expected.fields)
        for bad in [raw[:23], raw[:-1], zipped[:-1]]:
            with self.assertRaises(ValueError):
                cms.parse_record(bad)


if __name__ == "__main__":
    unittest.main()
