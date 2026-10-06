# ESP and Eorlund distribution audit — 2026-10-06

## Result and scope

The audited baseline was `main` at `0777e257`. Its xEdit builder cloned
`SteelMace` and changed `Model\\MODL`, but retained the source weapon's `WNAM`
first-person model reference. That is a concrete defect in this main branch's
builder; it is not a conclusion drawn from a different, earlier weapon project.
The source-contract test did not inspect WNAM and could report success despite
that defect. Baseline main did not contain an actual ESP.

The replacement build produces a regular Skyrim VR ESP with two new records:

| Record | Plugin-local ID | Purpose |
| --- | --- | --- |
| WEAP `CMS_ChainMorningstar` | `00000800` | One-handed mace, damage 44, weight 17, value 550 |
| STAT `CMS_ChainMorningstarFirstPerson` | `00000801` | First-person model object used by the WEAP's WNAM |

Both model paths are `weapons\\ChainMorningstarVR\\ChainMorningstar.nif`.
The only master is `Skyrim.esm`; there are no vanilla overrides, CONT records,
or LVLI records. The ESP is neither ESL-flagged nor localized. The file uses
form version 44 and HEDR version 1.7, consistent with the xEdit VR definitions.

`build/plugin/ChainMorningstarVR.esp` is 787 bytes. Its SHA-256 is
`789f4ec527f1b2ca77f72a48e18974922523030134addba157c6f625cbdf64b1`.
`build/plugin/ChainMorningstarVR.provenance.json` records the inputs, output
checksum, model bounds, and the explicit `in_game_validated: false` status.

Output sizes are 170 bytes for TES4, 152 bytes for STAT, and 417 bytes for WEAP,
including each 24-byte record header. Two additional 24-byte GRUP headers bring
the total to 787 bytes. The STAT and WEAP groups span 176 and 441 bytes.

## Input provenance

The build reads the user's existing private `ReferenceBundle.zip` export.
It does not extract data from an earlier custom MOD. The bundle describes its
records as original 24-byte Skyrim record headers plus their stored payloads.
Its collection warnings list is empty. The builder verifies each input's
SHA-256 against the bundle manifest before decoding or using it.

| User-provided original record | Size | SHA-256 |
| --- | ---: | --- |
| `Skyrim.esm`, WEAP `00013988`, EDID `SteelMace` | 532 bytes: 24-byte header + 508-byte payload | `c4c98cfa7a17ab64f08bf76510644bdcaa8d6bbcb44ea3c6de5e743da6a4a17f` |
| `Skyrim.esm`, CONT `0010FDE6`, EDID `MerchantWhiterunEorlundChest` | 339 bytes: 24-byte header + 315-byte payload | `e48a031481d40aaaa9efffd6bbe8a353abff57e0a2961373b210bb77efc64ba2` |

These hashes establish consistency with the supplied collection manifest;
they are not a claim of independent verification against Bethesda's release
hashes. No original record blobs or whole game files are embedded in the
public source tree or synthetic test fixtures.

## Record decisions

The original source WEAP has model `Weapons\\Steel\\SteelMace.nif` and
WNAM `00014305`. The old builder left that WNAM intact. The new ESP changes it
to its own STAT, stored as file FormID `01000801` because Skyrim.esm occupies
master index 00 and the ESP occupies index 01. The runtime continues to resolve
the WEAP by plugin name and local ID, independent of actual load order.

The following original fields are retained byte-for-byte. They are native mace
metadata; retaining them does not implement physical chain collision or chain
movement audio.

| Field | Original reference/value | Retention rationale |
| --- | --- | --- |
| ETYP | `00013F42` | Original equip-type link |
| BIDS | `000193C7` | Original block/bash impact-data link |
| BAMT | `000774C1` | Original alternate block-material link |
| KSIZ/KWDA | 3 keywords: `0001E719`, `0001E714`, `0008F958` | Native mace/material/vendor classification |
| INAM | `000193B7` | Original impact-data link |
| TNAM | `00105D43` | Original attack-fail sound link |
| NAM9/NAM8 | `0003DE2A` / `0003DE2B` | Original equip/unequip sound links |
| DNAM | 100 bytes, animation type 4 | One-handed mace speed, reach, skill, stagger, and native flags |
| CRDT | Original 24 bytes | Original critical data; critical damage remains 5 |
| VNAM | 1 | Original detection sound level |

Replaced: EDID, FULL, MODL, WNAM, DATA, and OBND. The generated STAT has an
authored DNAM with maximum angle 90, no directional material, and no snow flag.
Removed: source MODT texture hashes; MODS/MODD swaps if present; and DESC.
The original FULL/DESC are localized string IDs, so the output uses its own
plain FULL text and omits DESC. This avoids interpreting a source string-table
ID as text in the unlocalized plugin. Alternate textures belonging to SteelMace
are not allowed to replace materials from the new NIF.

OBND is the outward-rounded bind-pose geometry bound from the new reference
mesh, in Skyrim units: minimum `(-16, -21, -12)`, maximum `(16, 119, 12)`.
The asset agent calculated its continuous bounds from all 23,205 vertices after
their node transforms. OBND is not the attack collider and is not proof of hit
registration.

## Eorlund stock behavior

The user-provided CONT record independently confirms the target ID and editor
ID, and DATA flag `0x02` (Respawns). At SKSE DataLoaded, the retained runtime
distribution path checks the weapon's type, statistics, VendorItemWeapon,
custom first-person STAT link, and the chest's respawn flag. It adds one weapon
only when the base-container count is zero. Positive preexisting stock is
preserved; negative counts are rejected before mutation. Repeated successful
calls do not add another item.

This mutates the winning process-memory container base, not an ESP override.
The CommonLib container implementation edits the base `containerObjects`
entries. It does not reset an already-instantiated merchant reference inventory
and it does not establish that the barter menu has refreshed. Existing saves
may require the merchant's normal restock/reset before the new base item is
visible. A mod that replaces Eorlund's merchant container reference can also
bypass this specific chest. The runtime currently does not follow an arbitrary
replacement merchant-faction/container setup.

The log's base-injection success is therefore not equivalent to an observed
purchase. In-game verification must check appearance in Eorlund's stock,
purchase, reopening barter without duplication, save/load, and a normal restock.

## Validation performed and remaining gates

Performed:

- Input manifest checksum, record signature/ID/editor-ID, form-version, source
  layout, source mace type, source keyword, and vendor respawn checks.
- Independent parse of the actual 787-byte output, including record/group
  boundaries, exact two-record inventory, internal WNAM reference, statistics,
  model paths, bounds, and byte-for-byte preservation of retained source fields.
- Three binary regression tests using synthetic records: output structure and
  retained references; wrong/unsupported input rejection; and compression and
  truncation handling. All passed.
- Updated distribution source-contract lint. It passes and now explicitly
  identifies itself as source lint, not a merchant/game test.

Not performed here: TES5VREdit Check for Errors, execution of the optional
xEdit scripts inside xEdit, and Skyrim VR loading/barter/equip/restock tests.
The binary ESP therefore has structural validation, not a game-verified release
claim. The xEdit scripts remain an alternate build/check path; running them is
not needed to produce the already-generated ESP.

## Primary technical sources

- [xEdit Skyrim definitions: WEAP WNAM, STAT DNAM, CONT DATA, and VR header version](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsTES5.pas).
  Inspected file blob SHA `1c8d49ea0f14b55d71cf07a6320412983793d943`.
- [xEdit common definitions: OBND structure](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsCommon.pas).
  Current definitions use Min/Max vectors; the alternate xEdit builder also
  handles a six-field OBND layout by position.
- [CommonLibSSE-NG TESObjectWEAP declaration: firstPersonModelObject / WNAM](https://github.com/alandtse/CommonLibSSE-NG/blob/ng/include/RE/T/TESObjectWEAP.h).
  Inspected file blob SHA `0dbb9bbcd266ce42c7b051491da3fab6cd9067e0`.
- [CommonLibSSE-NG TESContainer implementation: base inventory additions/counts](https://github.com/alandtse/CommonLibSSE-NG/blob/ng/src/RE/T/TESContainer.cpp).
  Inspected file blob SHA `cfcd88f034d0195f90492a62bd6f0648c8b66802`.
  This upstream revision calls its count helper `GetObjectCount`; the project's
  pinned dependency exposes the earlier `CountObjectsInContainer` name.
- The private user-provided original record bytes and manifest above establish
  the concrete vanilla IDs and retained data used by this build.

No remote push was made by this audit task.
