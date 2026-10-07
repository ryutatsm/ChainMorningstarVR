# Audit4 — enemy head and hand equipment drops

The user reports normal motion with audit3 and requests a one-in-three chance
to drop equipment on head/hand contact. The original weapon-disarm requirement
defines hand equipment here as a held weapon or shield, not gauntlets.
This is a runtime-test distribution, not a claim of completed VR validation.

## Incoming evidence

Feedback `CMS-feedback-20261007-130041.zip`, SHA-256
`32f1bab13d404b500e59eb308ee0c9b5dbaf640b961c093075c0e9194c2f8700`,
contains audit3 logs. Holds of 13,184 ms and 20,119 ms end with normal trigger
releases; no warning/error line was observed. The user's motion confirmation is
accepted as an observation of that build, not automatic approval of every gate.

Nine routed contacts were logged: six `not-enemy` and three
`no-eligible-worn-instance`. All three latter contacts were head hits with zero
item/instance identity. No lottery or dropped reference was observed. These
records cannot establish a probability defect or prove a helmet was present.

## Implemented changes

- Exact `NPC Head [Head]` collision selects the worn head/hair/circlet instance,
  in that priority order. Existing head-drop policy and removal path remain.
- Exact left/right hand ragdoll bodies now select that hand's drawn weapon or
  shield. Forearm, torso and character-controller contacts are not substituted.
- Actual held weapon/shield collision or readable mesh contact also selects
  that item. Shields are armor, use shield biped slots and usually `ExtraWorn`;
  the previous weapon-only/`ExtraWornLeft` path could not handle them.
- Identical dual-wield base forms require exact attachment and worn-list
  ownership. Ambiguous shared weapon lists fail closed. Two-handed weapons use
  their right inventory slot for both physical hands and their own surface.
- A long mesh overlap remains active in the common native/mesh episode tracker.
  Previously its 100 ms cooldown could expire while it was still touching,
  permitting a later native hand contact to draw again. Only proven separation
  or removal of the equipped instance ends that mesh overlap.
- The unchanged unbiased three-way lottery is consumed once per eligible
  distinct episode, including losses. All eligible outcomes now log slot and
  physical surface. The collector distinguishes lottery wins from actual
  returned drop references, and records missing-reference errors separately.
- `RemoveItem(..., kDropping, exactExtraList, ...)` drops the existing item and
  its extra data. No base-form spawn, pre-unequip, random inventory replacement
  or retry occurs. Teammates/player, quest and non-playable items are excluded.

Audit3 motion code, appearance, authored scale, link count, impact sound and
blood geometry are unchanged. `main` is not merged or replaced.

## Verification scope

All 17 portable C++23 suites passed strict warnings. The three equipment/episode
suites passed AddressSanitizer and UBSan (executor LeakSanitizer disabled).
Exact ternary outcomes are tested independently for head, left hand and right
hand; the existing 300,000-contact RNG sample also passes. Tests cover empty
hands, shield armor flags, identical dual wield, two-handed shared ownership,
long overlap, stale mesh token removal, separation and non-target bones.

Two negative controls compile successfully then fail the intended assertions:
restoring the old cooldown-only native condition permits the extra draw during
a long overlap; restoring the left-weapon worn rule rejects a worn shield.
The Windows collector fixture includes old/new contact log formats and checks
slot/surface counts, eligible draws, wins, references and missing references.
Windows DLL and asset CI results and source hashes are recorded in the delivered
`BUILD_PROVENANCE.json`; CI success is separate from real VR observation.

VR still must establish head/right/left equipment drops, correct dual-wield and
two-handed selection, visible/pickable dropped references and preserved item
upgrades. Modified skeletons or inaccessible item meshes can be skipped. Fatal
hits retain the existing still-worn-instance recheck and must be distinguished
from Skyrim's ordinary death drops. See `DIAGNOSTIC_TEST_AUDIT4_JA.txt` and the
remaining formal checks in `RELEASE_GATE_NEW_BUILD.md`.
