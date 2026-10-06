from pathlib import Path

root = Path(__file__).resolve().parents[1]

build = (root / "Source/xEdit/Build_ChainMorningstarVR.pas").read_text(encoding="utf-8")
validate = (root / "Source/xEdit/Validate_ChainMorningstarVR.pas").read_text(encoding="utf-8")
vendor = (root / "Source/SKSE/PluginSkeleton/EorlundVendor.cpp").read_text(encoding="utf-8")
plugin = (root / "Source/SKSE/PluginSkeleton/PluginSkeleton.cpp").read_text(encoding="utf-8")

# The ESP must remain conflict-free: no vanilla merchant/container/leveled-list override.
for forbidden in (
    "MerchantWhiterunEorlundChest",
    "GroupBySignature(DstFile, 'CONT')",
    "GroupBySignature(DstFile, 'LVLI')",
    "Container Item Distributor",
):
    if forbidden in build:
        raise SystemExit(f"Build script contains forbidden vendor-distribution token: {forbidden}")

# Stable weapon ABI between xEdit output and the SKSE runtime.
for required in (
    "CMS_ChainMorningstar",
    "SetLoadOrderFormID(Dst, (GetLoadOrderFormID(Dst) and $FF000000) or $00000800)",
    "SetElementNativeValues(Dst, 'DATA\\Damage', 44)",
    "SetElementNativeValues(Dst, 'DATA\\Weight', 17.0)",
    "SetElementNativeValues(Dst, 'DATA\\Value', 550)",
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
        raise SystemExit(
            f"{script_name} contains a potentially unsafe non-short-circuit Assigned(...) and (...) expression"
        )
    if "lowercase(wbappname) <> 'tes5vr'" not in lowered:
        raise SystemExit(f"{script_name} is missing TES5VR mode guard")

# Validator must independently prove the record is the intended sellable one-hand mace.
for required in (
    "(GetLoadOrderFormID(WeaponRec) and $00FFFFFF) <> $00000800",
    "GetElementNativeValues(WeaponRec, 'DNAM\\Animation Type') <> 4",
    "VendorItemWeapon",
    "GroupBySignature(ModFile, 'CONT')",
    "GroupBySignature(ModFile, 'LVLI')",
    "Unexpected CONT override found",
    "Unexpected LVLI override found",
):
    if required not in validate:
        raise SystemExit(f"Validator missing required guard: {required}")

# Vendor injection is internal to ChainMorningstarVR.dll and must be idempotent.
for required in (
    "kChainMorningstarLocalFormID = 0x00000800",
    "kEorlundMerchantChestLocalFormID = 0x0010FDE6",
    'kPluginName = "ChainMorningstarVR.esp"',
    'kSkyrimMaster = "Skyrim.esm"',
    "LookupForm<RE::TESObjectWEAP>",
    "LookupForm<RE::TESObjectCONT>",
    'HasKeywordByEditorID("VendorItemWeapon")',
    "CountObjectsInContainer(weapon)",
    "if (before > 0)",
    "AddObjectToContainer(weapon, 1, nullptr)",
    "if (after != 1)",
):
    if required not in vendor:
        raise SystemExit(f"Eorlund runtime injector missing safety contract: {required}")

if "EnsureEorlundSellsChainMorningstar();" not in plugin:
    raise SystemExit("Plugin DataLoaded path does not invoke Eorlund runtime injection")

# No stale distributor configuration may ship; it would risk duplicate vendor stock.
cid_files = list(root.rglob("*_CID.ini"))
if cid_files:
    raise SystemExit(f"Stale CID configuration present: {cid_files}")

print("VENDOR_RUNTIME_CONTRACT_PASS")
print("weapon_local_formid=00000800")
print("target_container=0010FDE6 Skyrim.esm")
print("vendor_count=1 idempotent=true")
print("external_distributor_dependency=none")
print("plugin_record_conflicts=CONT:0 LVLI:0")
