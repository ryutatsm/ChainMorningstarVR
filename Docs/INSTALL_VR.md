# ChainMorningstarVR — Skyrim VR install/test procedure

## Required runtime
- Skyrim VR
- SKSEVR
- PLANCK (validated target build: 80100)

No external item-distribution framework is required. Eorlund Gray-Mane's stock is patched
in memory by ChainMorningstarVR.dll itself at SKSE DataLoaded.

## Vendor implementation
ChainMorningstarVR.esp contains only the new weapon record and deliberately contains no CONT or
LVLI override. The weapon has a fixed plugin-local FormID 00000800.

At DataLoaded, ChainMorningstarVR.dll:
1. resolves ChainMorningstarVR.esp|00000800,
2. verifies it is a one-hand mace and has VendorItemWeapon,
3. resolves MerchantWhiterunEorlundChest [CONT:0010FDE6] from Skyrim.esm,
4. checks whether that base container already contains the weapon,
5. adds exactly one item only when the current count is zero,
6. verifies the resulting count is exactly one and logs the result.

This modifies the process's in-memory winning container base record and creates no merchant-container
or leveled-list override in the ESP. Once a merchant reference inventory is instantiated, Skyrim's
normal save/restock behavior applies to that inventory just as it does to vanilla vendor stock.

On an existing save whose merchant inventory is already instantiated, the new base item may not
appear until Eorlund's merchant inventory next resets/restocks. Do not force-reset inventory
during the first safety test; allow a normal vendor restock if necessary.

## xEdit build stage
Use current xEdit in Skyrim VR mode. Correct VR mode is selected by either running TES5VREdit.exe
or launching xEdit with -TES5VR. Both bundled scripts independently check wbAppName and refuse to
run unless it is TES5VR.

Before building, make sure no existing ChainMorningstarVR.esp is present in the active Data path.
Back up and remove/rename any old file with that exact name so AddNewFileName can create a clean plugin.

Copy these files into the xEdit installation's Edit Scripts folder:
- Build_ChainMorningstarVR.pas
- Validate_ChainMorningstarVR.pas

For the build pass, load only Skyrim.esm. The build script reads SteelMace [WEAP:00013988],
copies it as a new record, fixes the new record's plugin-local FormID to 00000800, and sets the
project values using xEdit native numeric APIs.

For the validation pass, restart TES5VREdit and select only ChainMorningstarVR.esp; xEdit will
select Skyrim.esm because it is the plugin's required master. Run Validate_ChainMorningstarVR,
then xEdit Check for Errors.

Required validator result:
- local FormID 00000800
- EDID CMS_ChainMorningstar
- one-hand mace (DNAM Animation Type 4)
- VendorItemWeapon keyword present
- Damage 44
- Weight 17
- Value 550
- Model weapons\ChainMorningstarVR\ChainMorningstar.nif
- zero CONT overrides
- zero LVLI overrides

## First target-machine test
Use the READ-ONLY diagnostic DLL first. Do not use the native-proxy-test DLL until the diagnostic
log shows a plausible VRMeleeData layout on the target Skyrim VR install.

Verify:
1. Vortex deployment has no unexpected file conflicts.
2. ChainMorningstarVR.esp is enabled.
3. ChainMorningstarVR.log contains successful plugin load, PLANCK build 80100 detection,
   Eorlund vendor injection PASS, and the expected read-only VRMeleeData diagnostics.
4. Eorlund sells one Chain Morningstar after his merchant inventory is initialized or normally restocked.
5. Reopening the barter menu does not create duplicate Chain Morningstars.
6. Animated chains reupload requires no conflict rule against this mod.
