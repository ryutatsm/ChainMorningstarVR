# Native contacts and one-third equipment drops

Status: source integration implemented; Windows compilation and in-game behavior
must be validated separately. A passing portable policy test does not establish
that an NPC's runtime collider or a modded weapon mesh is readable.

## Contact evidence and lifetime

`NativeContactRouter` receives contact-point and collision-removed events from
the listener installed on the exact HIGGS body that the backend has configured
as the moving iron-ball compound. Both bodies in each callback are compared
against the registered source identity. The source hand and nonzero generation
must also match. Generic `TESHitEvent`, PLANCK hit messages, proximity to a hand,
and HIGGS' anonymous collision callback are not accepted as contact evidence.

Before the next physics step, the game thread snapshots nearby loaded actors:

- A head contact requires the actual collision body on `NPC Head [Head]`.
  Neck, torso, character-controller and hand bodies never count as head hits.
- Head equipment is the currently worn head-slot item, or hair-slot item if
  absent, or circlet if both are absent. The exact worn `ExtraDataList` identity
  is resolved on the game thread. Ambiguous duplicate worn instances fail closed.
- A native weapon contact requires a collider inside the equipped weapon's own
  `BIPOBJECT.partClone` subtree. The actor's hand/arm collider is never substituted.
  The base form determines the equipped hand; identical dual-wield forms also
  require an unambiguous left/right hand ancestor of the actual weapon subtree.
  An extra-data stack marked worn in both hands is rejected: `RemoveItem` has
  no hand parameter, so the adapter cannot prove which copy it would remove.
- The 650-unit actor-origin radius only limits snapshot work. Being within that
  radius cannot produce an impact or an equipment drop.

The Havok callback reads this bounded snapshot and queues actor handles, opaque
body/node/root identities, form IDs, worn-instance identities, and the contact
position. It does not traverse scene graphs or inventory, invoke an actor
method, allocate queue memory, or mutate equipment. No queued pointer is later
dereferenced. The game thread resolves the actor handle, traverses its current
scene tree, and checks that the same root, node and collision body still exist.
It then re-resolves the exact still-worn instance before removing anything.
Changing equipment or replacing the actor's loaded 3D invalidates the request.

The companion equipped-weapon geometry collector can submit only a confirmed
head-compound/weapon-surface intersection through `SubmitWeaponMeshImpact`.
It shares the source-body/generation check, instance recheck, episode tracker,
monotonic impact serial and probability policy with native contacts. There is no
fallback to a bounding sphere or hand/head distance for equipment attribution.
The geometry collector's supported geometry formats and skip conditions are
recorded in its own integration documentation.

## Contact episodes and probability

`ContactEpisodeCore.hpp` aggregates manifold points and multiple native bodies
belonging to the same actor/equipment part. All points from continuous contact
share one opportunity. A collision-removed notification and at least 0.10 s of
separation are needed before a native collision can begin another episode; this
prevents brief manifold churn from repeatedly drawing. Native and exact-mesh
reports of the same strike are deduplicated. The mesh collector must retain its
strictly increasing episode token until it has proved geometric separation.

The router assigns one common, increasing serial per source hand on the game
thread. `EquipmentDropCore.hpp` consumes every eligible serial, including failed
random draws and no-longer-equipped items. `std::uniform_int_distribution(0, 2)`
provides an unbiased one-third chance; result zero permits the drop. Persistent
contact cannot reroll until it gets lucky. A bounded queue or episode table that
fills fails closed; skipped contact records do not retry.

## Dropping the actual equipped instance

The adapter checks that the player still holds the CMS weapon in the recorded
source hand, the target is an enemy and not the player or a teammate, and the
specified item is playable, not a quest object and still worn in the named slot.
It calls:

`Actor::RemoveItem(item, 1, kDropping, exactExtraList, ..., contactPosition)`

This uses Skyrim's equipped-item removal/drop path and keeps the item's existing
extra data, including enchantment and tempering. It never spawns a base-form
replacement, removes an arbitrary inventory copy, or unequips before resolving
the instance. A missing returned dropped reference is logged without retry:
retrying could remove a second item after a partially completed engine action.

Enemy/alive state is snapshotted before the physical step. If that physical hit
kills the actor before the queued drop runs, the snapshot permits the fatal-hit
case; the target must still not be a player teammate. A fresh contact against an
actor already dead when snapshotted is ineligible. Source/target lifetime and
worn-instance checks still apply. This is source behavior, not a claim that fatal
hits and death-triggered inventory scripts have been tested in Skyrim VR.

## Diagnostics

The first 24 routed impacts per source session, every 128th impact afterwards,
and successful drop decisions log collector, generation, body identity, actor,
part, item, worn-instance identity and outcome. Actual drop-reference success
or failure has a separate log line. Unmapped contact callback totals are
summarized at most once per five seconds when they change; ground/scenery and
non-equipment actor parts are expected to contribute. This distinguishes a
random losing draw from absent runtime head/weapon mapping without frame spam.

## Source evidence

- CommonLibSSE-NG v3.5.2 declares `NiCollisionObject::sceneObject`,
  `bhkNiCollisionObject::body`, `bhkRefObject::referencedObject`,
  `TESObjectREFR::GetBiped`, `BIPOBJECT::item/partClone`, `Actor::GetWornArmor`,
  `GetEquippedObject`, `GetInventory` and the exact `RemoveItem` signature.
  The implementation uses these declared interfaces, not an invented VR layout.
  [CommonLib headers](https://github.com/CharmedBaryon/CommonLibSSE-NG/tree/v3.5.2/include/RE)
- CommonLib's `InventoryEntryData` copy duplicates the list container but its
  entries still point to the original `ExtraDataList` instances.
  [Inventory copy semantics](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/v3.5.2/src/RE/I/InventoryEntryData.cpp)
- HIGGS demonstrates actual equipped-instance drops in
  `Hand::SpawnEquippedSelectedObject`, and distinguishes weapon-subtree collision
  from an attached hand collider while inspecting biped parts. Only actual
  weapon-subtree collision is accepted here.
  [HIGGS hand implementation](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hand.cpp)
- PLANCK's experimental NPC weapon-body activation was commented out in the
  audited source. A hand hit cannot therefore stand in for a weapon-surface hit;
  unreadable weapon geometry must be skipped by the exact-mesh collector.
  [PLANCK implementation](https://github.com/adamhynek/activeragdoll/blob/f06fc953334aeea912975af6302e52e1bad92b01/src/main.cpp)

## Validation and remaining runtime cases

Portable tests cover exact three-outcome mapping, a 300,000-impact RNG sample,
wrong body/generation, duplicate serials, changing equipment, non-enemies and
non-droppable equipment. The contact-episode suite additionally covers 1,000
persistent callbacks, overlapping target colliders, removed/recreated manifold
churn, independent hands/targets/parts, mesh/native duplicate suppression,
consumed rejected mesh tokens, reset and invalid numeric input. The new suite
passes strict C++23 warnings plus AddressSanitizer/UBSan (LeakSanitizer disabled
in the executor).

In-game checks remain necessary for humanoid head-body availability, nonstandard
race skeletons, NPC equipment mesh accessibility, two identical dual-wield
weapons, custom enchanted/tempered instances, quest objects, no helmet,
followers, fatal hits, load/cell changes and equipment swaps during contact.
The exact dropped reference must exist and the actor must lose exactly one
matching instance. No game runtime result has been inferred from source or CI.
