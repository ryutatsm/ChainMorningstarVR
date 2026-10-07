#!/usr/bin/env python3
"""Build a regular Skyrim VR ESP from the user's private ReferenceBundle.

No game record bytes are embedded in this source. The input WEAP is read from
the user's installation export and checked against its collection manifest.
Record layouts: TES5Edit/Core/wbDefinitionsTES5.pas (WEAP, STAT, TES4).
This is a structural build, not a substitute for xEdit and in-game validation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib

HEADER = struct.Struct("<4sIIIIHH")
SUBHEADER = struct.Struct("<4sH")
WEAPON_ID = 0x01000800  # One master: Skyrim.esm=00, this ESP=01.
FIRST_PERSON_ID = 0x01000801
MODEL = b"weapons\\ChainMorningstarVR\\ChainMorningstar.nif\0"
SOURCE_WEAPON_ID = 0x00013988
CHEST_ID = 0x0010FDE6
VENDOR_KEYWORD = 0x0008F958
MAX_RECORD_BYTES = 1 << 20
AUDIO_RECORDS = [(0x01000802, 'CMS_IronScrape', 'iron_scrape.wav', True),
                 (0x01000803, 'CMS_AirCut', 'air_cut.wav', False),
                 (0x01000804, 'CMS_DisarmStrike', 'disarm_strike.wav', False)]


@dataclass(frozen=True)
class Record:
    signature: bytes
    flags: int
    form_id: int
    version: int
    fields: tuple[tuple[bytes, bytes], ...]

    def field(self, signature: bytes) -> bytes:
        found = [value for tag, value in self.fields if tag == signature]
        if len(found) != 1:
            raise ValueError(f"{self.signature!r}: expected one {signature!r}, got {len(found)}")
        return found[0]


def parse_record(raw: bytes) -> Record:
    if len(raw) < HEADER.size:
        raise ValueError("Truncated record header")
    sig, size, flags, form_id, _, version, _ = HEADER.unpack_from(raw)
    if sig == b"GRUP" or size != len(raw) - HEADER.size or size > MAX_RECORD_BYTES:
        raise ValueError("Invalid record size/signature")
    data = raw[HEADER.size:]
    if flags & 0x40000:
        if len(data) < 4:
            raise ValueError("Truncated compressed record")
        expected, = struct.unpack_from("<I", data)
        if expected > MAX_RECORD_BYTES:
            raise ValueError("Compressed record exceeds size limit")
        inflater = zlib.decompressobj()
        data = inflater.decompress(data[4:], expected + 1)
        if len(data) != expected or not inflater.eof or inflater.unused_data:
            raise ValueError("Compressed record size/stream mismatch")
    fields = []
    at = 0
    while at < len(data):
        if at + SUBHEADER.size > len(data):
            raise ValueError("Truncated subrecord header")
        tag, length = SUBHEADER.unpack_from(data, at)
        at += SUBHEADER.size
        if tag == b"XXXX":
            # None of the narrowly supported vanilla records needs extended fields.
            raise ValueError("Extended subrecords are outside this builder's supported input")
        if at + length > len(data):
            raise ValueError("Truncated subrecord body")
        fields.append((tag, data[at:at + length]))
        at += length
    return Record(sig, flags, form_id, version, tuple(fields))


def encode_record(signature: bytes, form_id: int, fields: list[tuple[bytes, bytes]]) -> bytes:
    data = bytearray()
    for tag, value in fields:
        if len(tag) != 4 or len(value) > 65535:
            raise ValueError("Unsupported subrecord")
        data += SUBHEADER.pack(tag, len(value)) + value
    return HEADER.pack(signature, len(data), 0, form_id, 0, 44, 0) + data


def encode_group(signature: bytes, record: bytes) -> bytes:
    return struct.pack("<4sI4sIHHHH", b"GRUP", len(record) + 24, signature, 0, 0, 0, 0, 0) + record


def validate_source(weapon: Record, chest: Record) -> None:
    if (weapon.signature, weapon.form_id, weapon.version, weapon.field(b"EDID")) != (
        b"WEAP", SOURCE_WEAPON_ID, 44, b"SteelMace\0"
    ):
        raise ValueError("Expected Skyrim VR SteelMace WEAP 00013988, form version 44")
    if weapon.flags & ~0x40000:
        raise ValueError("Unexpected source weapon record flags")
    if len(weapon.field(b"DATA")) != 10 or len(weapon.field(b"DNAM")) != 100:
        raise ValueError("Unsupported weapon DATA/DNAM layout")
    if weapon.field(b"DNAM")[0] != 4:
        raise ValueError("Source is not a one-handed mace")
    if len(weapon.field(b"CRDT")) != 24:
        raise ValueError("Source critical data is not the Skyrim VR/SSE layout")
    fields = dict(weapon.fields)
    if len(fields) != len(weapon.fields):
        raise ValueError("Duplicate source weapon subrecords")
    # Scripts, enchantment, templates, destructibles and alternate model groups
    # require additional processing; never silently carry them into this weapon.
    supported = {b"EDID", b"OBND", b"FULL", b"MODL", b"MODT", b"MODS", b"MODD",
                 b"ETYP", b"BIDS", b"BAMT", b"YNAM", b"ZNAM", b"KSIZ", b"KWDA",
                 b"DESC", b"INAM", b"WNAM", b"SNAM", b"XNAM", b"NAM7", b"TNAM",
                 b"UNAM", b"NAM9", b"NAM8", b"DATA", b"DNAM", b"CRDT", b"VNAM"}
    if set(fields) - supported:
        raise ValueError(f"Unsupported source fields: {set(fields) - supported}")
    keyword_bytes = weapon.field(b"KWDA")
    if len(keyword_bytes) % 4:
        raise ValueError("Invalid KWDA size")
    keywords = struct.unpack(f"<{len(keyword_bytes)//4}I", keyword_bytes)
    if weapon.field(b"KSIZ") != struct.pack("<I", len(keywords)) or VENDOR_KEYWORD not in keywords:
        raise ValueError("Missing/inconsistent VendorItemWeapon keyword")
    if (chest.signature, chest.form_id, chest.version, chest.field(b"EDID")) != (
        b"CONT", CHEST_ID, 44, b"MerchantWhiterunEorlundChest\0"
    ):
        raise ValueError("Unexpected vendor chest source")
    if len(chest.field(b"DATA")) != 5 or not (chest.field(b"DATA")[0] & 2):
        raise ValueError("Vendor chest does not respawn")


def build_audio_records(template: Record) -> bytes:
    # Clone the user's verified standard, spatial physics descriptor metadata;
    # replace every sample with our original audio. No vanilla WAV is copied.
    if (template.signature, template.form_id, template.version, template.field(b'EDID')) != (
            b'SNDR', 0x3D128, 40, b'PHYChainSD\0'):
        raise ValueError('Expected verified Skyrim VR PHYChainSD template')
    if set(tag for tag, _ in template.fields) != {b'EDID', b'CNAM', b'GNAM', b'ANAM', b'ONAM', b'LNAM', b'BNAM'}:
        raise ValueError('Unsupported sound descriptor/conditions')
    for tag, size in [(b'CNAM',4),(b'GNAM',4),(b'ONAM',4),(b'LNAM',4),(b'BNAM',6)]:
        if len(template.field(tag)) != size: raise ValueError('Unsupported SNDR field size')
    records = b''
    for form_id, edid, name, loop in AUDIO_RECORDS:
        length = bytearray(template.field(b'LNAM'))
        length[1] = (length[1] & ~0x38) | (0x08 if loop else 0)
        fields = [(b'EDID', edid.encode()+b'\0'), (b'CNAM', template.field(b'CNAM')),
                  (b'GNAM', template.field(b'GNAM')),
                  (b'ANAM', ('fx\\ChainMorningstarVR\\'+name+'\0').encode()),
                  (b'ONAM', template.field(b'ONAM')), (b'LNAM', bytes(length)),
                  (b'BNAM', bytes([0,0,128,0,0,0]))]
        records += encode_record(b'SNDR', form_id, fields)
    return records


def build_plugin(weapon: Record, chest: Record, bounds: tuple[int, ...], sound_template: Record | None = None) -> bytes:
    validate_source(weapon, chest)
    if len(bounds) != 6 or any(bounds[i] >= bounds[i + 3] for i in range(3)):
        raise ValueError("Bounds must be xmin ymin zmin xmax ymax zmax")
    bound_bytes = struct.pack("<6h", *bounds)
    replacements = {b"EDID": b"CMS_ChainMorningstar\0", b"FULL": "チェーンドモーニングスター\0".encode("utf-8"),
                    b"MODL": MODEL, b"OBND": bound_bytes,
                    b"WNAM": struct.pack("<I", FIRST_PERSON_ID),
                    b"DATA": struct.pack("<IfH", 550, 17.0, 44)}
    for required in replacements:
        weapon.field(required)
    # Localized FULL/DESC integers are not strings. FULL is replaced; DESC is
    # absent rather than leaking a STRINGS-table ID into an unlocalized ESP.
    # MODT hashes and MODS/MODD overrides belong to the source NIF, not ours.
    removed = {b"DESC", b"MODT", b"MODS", b"MODD"}
    weapon_fields = [(tag, replacements.get(tag, value)) for tag, value in weapon.fields if tag not in removed]
    stat_fields = [(b"EDID", b"CMS_ChainMorningstarFirstPerson\0"), (b"OBND", bound_bytes),
                   (b"MODL", MODEL), (b"DNAM", struct.pack("<fIB3x", 90.0, 0, 0))]
    # HEDR counts two records and their two top-level groups. Regular ESP, no
    # ESL or localized flag; 0x802 is the first unused local form ID.
    audio = build_audio_records(sound_template) if sound_template else b''
    header = encode_record(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.7, 8 if audio else 4, 0x805 if audio else 0x802)),
                                        (b"CNAM", b"ChainMorningstarVR\0"),
                                        (b"SNAM", b"Private development build; in-game validation required.\0"),
                                        (b"MAST", b"Skyrim.esm\0"), (b"DATA", bytes(8)),
                                        (b"INCC", bytes(4))])
    return header + encode_group(b"STAT", encode_record(b"STAT", FIRST_PERSON_ID, stat_fields)) + encode_group(
        b"WEAP", encode_record(b"WEAP", WEAPON_ID, weapon_fields)) + (encode_group(b'SNDR', audio) if audio else b'')


def load_bundle_record(bundle: Path, manifest: dict, signature: str, form_id: int) -> tuple[Record, str]:
    matches = [r for r in manifest["records"] if r["source"] == "Skyrim.esm" and
               r["signature"] == signature and r["form_id_hex"].upper() == f"{form_id:08X}"]
    if len(matches) != 1:
        raise ValueError(f"Expected one manifest entry for {signature} {form_id:08X}")
    entry = matches[0]
    path = (bundle / entry["bundle_member"]).resolve()
    if not path.is_relative_to(bundle.resolve()):
        raise ValueError("Manifest record path escapes bundle")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["sha256"]:
        raise ValueError("Source record does not match its collection manifest SHA-256")
    return parse_record(raw), digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--with-audio', action='store_true', help='Add original sound descriptors 802-804 (scrape loop, swing and disarm one-shots)')
    parser.add_argument("--bounds", type=int, nargs=6, required=True,
                        metavar=("XMIN", "YMIN", "ZMIN", "XMAX", "YMAX", "ZMAX"))
    args = parser.parse_args()
    manifest = json.loads((args.reference_bundle / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("warnings"):
        raise ValueError("Review ReferenceBundle collection warnings before building")
    weapon, weapon_hash = load_bundle_record(args.reference_bundle, manifest, "WEAP", SOURCE_WEAPON_ID)
    chest, chest_hash = load_bundle_record(args.reference_bundle, manifest, "CONT", CHEST_ID)
    sound_template, sound_hash = load_bundle_record(args.reference_bundle, manifest, 'SNDR', 0x3D128) if args.with_audio else (None, None)
    output = build_plugin(weapon, chest, tuple(args.bounds), sound_template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    report = {"plugin": args.output.name, "plugin_sha256": hashlib.sha256(output).hexdigest(),
              "input_weapon_sha256": weapon_hash, "input_chest_sha256": chest_hash,
              "records": {"WEAP": "00000800", "STAT": "00000801"},
              "masters": ["Skyrim.esm"], "form_version": 44, "damage": 44, "weight": 17,
              "value": 550, "bounds": args.bounds, "overrides": [], "in_game_validated": False}
    report['builder_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if sound_template:
        report['input_sound_template_sha256'] = sound_hash
        report['records']['SNDR'] = [f'{r[0] & 0xffffff:08X}' for r in AUDIO_RECORDS]
        report['audio_paths'] = ['sound/fx/ChainMorningstarVR/'+r[2] for r in AUDIO_RECORDS]
    args.output.with_suffix(".provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
