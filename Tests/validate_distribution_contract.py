from pathlib import Path
import configparser

root = Path(__file__).resolve().parents[1]

build = (root / "Source/xEdit/Build_ChainMorningstarVR.pas").read_text(encoding="utf-8")
validate = (root / "Source/xEdit/Validate_ChainMorningstarVR.pas").read_text(encoding="utf-8")
cid_path = root / "Distribution/ChainMorningstarVR_CID.ini"

# Build script must create only the weapon record. Vendor distribution belongs to CID.
for forbidden in (
    "MerchantWhiterunEorlundChest",
    "GroupBySignature(DstFile, 'CONT')",
    "GroupBySignature(DstFile, 'LVLI')",
):
    if forbidden in build:
        raise SystemExit(f"Build script contains forbidden vendor override token: {forbidden}")

for required in (
    "CMS_ChainMorningstar",
    "DATA\\Damage', '44",
    "DATA\\Weight', '17.000000",
    "DATA\\Value', '550",
    "weapons\\ChainMorningstarVR\\ChainMorningstar.nif",
):
    if required not in build:
        raise SystemExit(f"Build script missing required weapon contract: {required}")

# xEdit/JvInterpreter does NOT short-circuit boolean and/or. Guard nil objects in nested ifs.
for script_name, script_text in (
    ("Build_ChainMorningstarVR.pas", build),
    ("Validate_ChainMorningstarVR.pas", validate),
):
    lowered = script_text.lower()
    if "assigned(" in lowered and ") and (" in lowered:
        raise SystemExit(f"{script_name} contains a potentially unsafe non-short-circuit Assigned(...) and (...) expression")

# Both scripts must fail closed outside Skyrim VR xEdit mode.
for script_name, script_text in (
    ("Build_ChainMorningstarVR.pas", build),
    ("Validate_ChainMorningstarVR.pas", validate),
):
    if "lowercase(wbappname) <> 'tes5vr'" not in script_text.lower():
        raise SystemExit(f"{script_name} is missing TES5VR mode guard")

# Validator must explicitly reject container and leveled-list overrides.
for required in (
    "GroupBySignature(ModFile, 'CONT')",
    "GroupBySignature(ModFile, 'LVLI')",
    "Unexpected CONT override found",
    "Unexpected LVLI override found",
):
    if required not in validate:
        raise SystemExit(f"Validator missing conflict guard: {required}")

cfg = configparser.ConfigParser(strict=True)
cfg.optionxform = str
cfg.read(cid_path, encoding="utf-8")
if list(cfg.sections()) != ["General"]:
    raise SystemExit(f"Unexpected CID sections: {cfg.sections()}")

items = dict(cfg.items("General"))
expected = {"0x10FDE6~Skyrim.esm": "CMS_ChainMorningstar|1"}
if items != expected:
    raise SystemExit(f"CID distribution mismatch: {items!r}")

print("CID_CONTRACT_PASS")
print("target=0x10FDE6~Skyrim.esm")
print("item=CMS_ChainMorningstar count=1")
print("plugin_record_conflicts=CONT:0 LVLI:0")
