# ChainMorningstarVR — Skyrim VR install/test procedure

## Required runtime
- Skyrim VR
- SKSEVR
- PLANCK (validated target build: 80100)
- Container Item Distributor (CID) 2.1.3 or a later VR-compatible release
- powerofthree's Tweaks VR
- VR Address Library for SKSEVR

CID is used only for Eorlund Gray-Mane's vendor stock. The weapon ESP intentionally contains
no merchant-container or leveled-list override.

## Why CID
Directly overriding MerchantWhiterunEorlundChest or VendorEorlundSkyforgeSteelSet creates
normal plugin record conflicts. CID adds the weapon to Eorlund's merchant container at runtime,
handles container resets, and avoids CONT/LVLI overrides in ChainMorningstarVR.esp.

## CID config
The release archive places this file in the Skyrim Data root:

    ChainMorningstarVR_CID.ini

Contents:

    [General]
    0x10FDE6~Skyrim.esm = CMS_ChainMorningstar|1

CID scans Data\*_CID.ini files. The target is Eorlund's merchant chest base container and the
item is resolved by the weapon's EditorID.

## xEdit build stage
Use current xEdit in Skyrim VR mode. Recommended: xEdit 4.1.5f or later.
Correct VR mode is selected by either renaming the executable to TES5VREdit.exe or launching
xEdit with -TES5VR. The first startup/log line must identify TES5VREdit / Skyrim VR mode.

Before building, make sure no existing ChainMorningstarVR.esp is present in the active Data path.
Back up and remove/rename any old file with that exact name so AddNewFileName can create a clean plugin.

Copy these files into the xEdit installation's Edit Scripts folder:

- Build_ChainMorningstarVR.pas
- Validate_ChainMorningstarVR.pas

For the build pass, load only Skyrim.esm. The build script reads SteelMace [00013988] directly and
does not need any other mod loaded. Run Build_ChainMorningstarVR and save ChainMorningstarVR.esp.

For the validation pass, restart TES5VREdit and select only ChainMorningstarVR.esp; xEdit will
automatically select Skyrim.esm because it is the plugin's required master. Then run
Validate_ChainMorningstarVR and xEdit Check for Errors.

Required validator result:
- WEAP CMS_ChainMorningstar
- Damage 44
- Weight 17
- Value 550
- Model weapons\ChainMorningstarVR\ChainMorningstar.nif
- zero CONT overrides
- zero LVLI overrides

## First target-machine test
Use the READ-ONLY diagnostic DLL first. Do not use the native-proxy-test DLL until the
diagnostic log shows a plausible VRMeleeData layout on the target Skyrim VR install.

Verify:
1. Vortex deployment has no unexpected file conflicts.
2. ChainMorningstarVR.esp is enabled.
3. CID and its VR dependencies load without errors.
4. Eorlund sells one Chain Morningstar after vendor inventory initializes/resets.
5. ChainMorningstarVR.log contains the expected read-only diagnostics.
6. ContainerItemDistributor.log contains a successful distribution for the Eorlund chest.
