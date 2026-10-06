# 0.8.0: 75% size, five extra links, iron impacts and weapon blood

The user reported 0.7.0 working normally. The supplied 20261006-203748 log
confirms HIGGS head attachment, continued native physics steps and chain sweeps.
The three initial chain diagnostic samples contained no chain contacts, so that
log alone does not certify chain/obstacle response or successful equipment drops.
The final requested extension is **five** links, not three: 14 → 19.

## Dimensions and existing behavior

`Source/SKSE/WeaponDimensions.hpp` is shared by the runtime and the Python asset
generator. The 0.75 factor is baked once into all mesh positions, node offsets,
convex vertices, plane distances and margins. The native clone's expected bounds,
CPU contact planes and chain capsule sizes follow the same change. VRIK/actor
scale is still handled by the existing live scene path. Root scale stays 1.

| Quantity | 0.8.0, before live actor/VRIK scale |
| --- | --- |
| Handle length | 0.42 m |
| Links | 19 |
| Link centre spacing | 0.04846153846 m |
| First-to-last centre span | 0.87230769231 m |
| Anchor-to-head centre reach | 1.04105769231 m |
| Extra length over a 75%-size 14-link chain | 0.24230769231 m |
| Core / spike-tip radius | 0.12 / 0.18 m |

The 12 kg solver mass, damping, low restitution, dark finish, sculpted dents,
UVs, curved emblem and one-in-three equipment policy remain. Inventory weight
is still 17. The NIF body's core-sphere inertia estimate now uses its actual
12 kg mass and scaled radius, instead of the older 8 kg / 16 cm values.
All 19 link centres use the same query and solver path; links still have no
attack bodies, damage or equipment-drop draws. There are no self-collisions or
two-way forces from chain links to objects/NPCs.

## Heavy metal impact audio

The private ReferenceBundle's `MaterialHeavyMetal` (MATT 00012F3B) refers to
`PHYGenericMetalHeavyImpactSet` (IPDS 0005CF05), whose material entries resolve
to `PHYGenericMetalHeavyImpact` (IPCT 0005CEFB). The latter contains quiet
SNAM 0005CEFA and loud NAM1 0005CEF9. The bridge reads the resolved IPCT's loud
descriptor, falling back to its quiet one. No game audio is redistributed.
The loud/quiet selection agrees with
[HIGGS hand.cpp](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hand.cpp).
The BGSImpactData members come from pinned CommonLibSSE-NG v3.5.2
`67ba410068022e06ebf42cfca44274b0aa98a2da`, include/RE/B/BGSImpactData.h.

Only an actual head contact's closing-velocity response can request an impact.
The minimum estimated impulse is 3 kg·m/s and the cooldown is 0.22 seconds;
resting-gravity corrections do not produce repeated clanks. Chain rattle and
impact have separate bounded four-handle pools, so rattles cannot truncate the
iron sound. Impact starts at the head's world position; rattle follows the head.
All handles stop on release, load or teleport. The first three impact playback
requests per equip are logged, including whether Play accepted the request.

## Blood geometry and trigger ownership

The exporter combines the actual head metal, fourteen sculpted spikes and
curved emblem into two matching blood passes. Each has 27,651 vertices / 51,280
triangles, displaced 0.225 mm along the existing surface normals. They share the
animated `CMS_HeadNode` parent. The handle and chain have no blood geometry.
These passes are initially hidden and omitted from the clean GLB preview.

Shader, alpha and object flags were inspected directly in the user's vanilla
Skyrim VR ironmace.nif and steelmace.nif:

| Pass | Shader flags 1 / 2 | Alpha flags / threshold | Object flags |
| --- | --- | --- | --- |
| BloodFX | 2348810240 / 131072 | 21059 / 0 | 524303 |
| BloodLighting | 2386559361 / 0 | 21005 / 0 | 524303 |

BloodFX uses BSEffectShaderProperty with the Weapon_Blood flag. BloodLighting
uses the matching vanilla lighting material. References are the game's
BloodHitDecals01, BloodHitDecals01Add, BloodHitDecals01_n and EyeCubeMap DDS files.
Game weapon-blood processing owns activation, blood settings and fading. No
new hit hook, fabricated damage, collision-triggered tint or forced bleeding is
introduced. Consequently a wall or chain contact cannot request blood through
CMS. Engine/PLANCK blood activation on the nested moving head still requires
in-game confirmation, including blocked hits and non-bleeding enemies.

## Verification

- All 27 pre-existing visible meshes compared to the delivered 0.7.0 CMS input:
  positions ×0.75 (maximum text-rounding difference 7.5e-10 m), unchanged normals,
  UVs and triangle topology. Five appended link meshes are identical to link 00.
- Independent asset checks: 22 nodes, 32 visible meshes, 15 hulls; curved emblem
  closure, source-image UVs and spike clearance still pass at the new size.
- NIF save/reload: 34 shapes including the hidden blood pair, correct moving
  parent, per-vertex blood surface agreement and vanilla shader/alpha contracts.
- Ten portable C++ programs pass, including contacts for each appended link,
  actual-impact sound gating, frame rates 45–144 Hz, lifecycle and drop policy.
  Static distance-constraint error is 1.662 mm; 45/90 Hz trajectory difference
  is 1.47e-6 m. The heavy-head settling ratio against the lighter settings on
  the same 19-link layout is 0.232.
- Three ESP tests, four material tests, vendor-contract lint and the generated
  collision-plane check pass. Windows CI and packaging verify the same commit
  and complete source/output hashes; archive provenance carries the run IDs.

These checks do not run Skyrim VR. Sound balance, blood activation/fading,
surface appearance, collision alignment and combat need target-game testing.
