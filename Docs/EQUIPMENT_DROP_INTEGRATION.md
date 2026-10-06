# Equipment drop audit and integration contract

Status: **foundation only; not connected to gameplay and not runtime-verified**.
The plugin currently has no caller of `TryDropForConfirmedImpact` or
`BeginEquipmentDropSession`. This intentionally prevents a vanilla mace hit,
hand collision, or approximate head proximity from masquerading as contact by
the independently moving iron ball.

## Implemented

- `EquipmentDropCore.hpp`: one unbiased random outcome from `{0, 1, 2}` for each
  eligible physical impact, with only `0` permitting a drop. Both a win and a
  loss consume the impact, so sustained contact cannot repeat the draw.
- A nonzero world/body generation and exact owned `hkpRigidBody` identity are
  required. The contact body's identity must match the body registered for that
  source hand. Ordinary `TESHitEvent` data cannot supply that identity.
- Per-hand strictly increasing impact serials reject duplicates and stale
  callbacks. The future collector must retain the same serial for a continuous
  contact episode, aggregate manifold points, and deliver episodes in order.
- `EquipmentDrop.cpp`: a game-thread adapter checks the equipped CMS weapon,
  enemy actor, struck equipment category, exact base form and exact currently
  worn `ExtraDataList`. It selects the hit hand's weapon, not an arbitrary copy.
- Head equipment is restricted to an already identified worn armor item using
  a head, hair or circlet slot. The adapter does not randomly choose armor from
  the actor's inventory. A future head-contact mapper must select one actual
  worn head item and its instance before requesting the drop.
- Nonplayable equipment and quest objects are excluded. Followers, the player,
  nonhostile actors and actors already dead at processing time are excluded.
- The adapter calls `Actor::RemoveItem(item, 1, kDropping, exactExtraList, ...)`.
  It does not spawn a base-form copy, erase enchantments/tempering, or separately
  unequip before resolving the instance. A failed returned reference is logged
  without retrying the same impact.

## Primary source findings

1. PLANCK revision 1 exposes `PlanckHitEvent` / `PlanckHitData`, including the
   struck Ni node and source hand. The hit event itself does not identify the
   specific source rigid body or prove that our simulated iron ball caused it.
   [Interface at audited commit](https://github.com/adamhynek/activeragdoll/blob/f06fc953334aeea912975af6302e52e1bad92b01/include/planckinterface001.h)
2. PLANCK sets its extended node information inside `HitActor` and dispatches
   the extended event from its normal hit-data path. Its experimental code to
   activate NPC equipped-weapon physics bodies is commented out, including a
   TODO for offhand weapons. A hand bone hit is therefore not evidence that
   the enemy's sword, axe or mace surface was struck.
   [Hit and weapon-body implementation](https://github.com/adamhynek/activeragdoll/blob/f06fc953334aeea912975af6302e52e1bad92b01/src/main.cpp)
3. HIGGS' public `CollisionCallback` reports only a hand flag, mass and separating
   velocity. It exposes no target actor, target body or target equipment.
   Its collision-filter callback is a broadphase/filter question, not impact
   evidence. Its own `SpawnEquippedSelectedObject` demonstrates an actual
   equipped-instance drop with `RemoveItem` reason 3 and the exact extra list.
   [HIGGS API](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/include/higgsinterface001.h)
   [HIGGS equipment implementation](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hand.cpp)
4. The adapter's method signatures were checked against the project's Conan
   CommonLibSSE-NG **v3.5.2**, including `RemoveItem`, `GetInventory`,
   `GetEquippedObject`, `GetPlayable`, `IsQuestObject`, and worn extra-data types.
   CommonLib's inventory entry copy duplicates the list container, while the
   contained pointers still name the original extra-data instances.
   [Actor header](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/v3.5.2/include/RE/A/Actor.h)
   [Form header](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/v3.5.2/include/RE/T/TESForm.h)
   [Inventory copy semantics](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/v3.5.2/src/RE/I/InventoryEntryData.cpp)

A future PLANCK diagnostic listener also needs an ABI-aware marker check:
PLANCK stores a 32-bit marker at TESHitEvent offset `0x18`; CommonLib declares
an 8-bit flag there plus padding. Reading only `event->flags` loses the marker.
No such listener or structure reinterpretation is part of this implementation.

## Required before activation

1. Own a real iron-ball body and verify its shape, transform, velocity and
   lifetime in the Skyrim Havok world. Register that same body's identity with
   the equipment policy, and invalidate it on unequip/load/cell changes.
2. Obtain real head-body and enemy equipped-weapon surface contacts. The latter
   needs a verified target collider or exact geometry collision approach; do
   not substitute distance to the hand/head or a generic hit event.
3. Map a contacted enemy weapon to its exact hand, base form and equipped
   instance. Record target identity safely and perform inventory changes only
   on the game thread, outside Havok callbacks.
4. Preserve enemy state at impact for fatal hits. The current conservative
   adapter skips actors dead when it executes; killing-blow behavior remains
   an explicit integration test requirement.
5. Verify dual-wield identical base weapons, tempered/enchanted copies, quest
   items, no helmet, followers, persistent contact, alternating contact points,
   load/unload, target death, and equipment changes between contact and handling.
6. Verify the resulting dropped reference exists in the world and that the
   actor loses exactly one matching instance. Successful portable policy tests
   do not establish any of these runtime behaviors.

## Validation performed

`Tests/equipment_drop_ci.cpp` verifies the exact three-outcome mapping, a
300,000-impact seeded RNG frequency check, one draw across 1,000 repeat contact
callbacks, consumed losing draws, wrong-body rejection, source-hand separation,
wrong-generation rejection, invalid identities, nonhostile targets, absent or
changed equipment, and non-droppable items. It passed strict C++23 compilation
with `-Wall -Wextra -Werror -pedantic` and AddressSanitizer/UBSan. LeakSanitizer
cannot inspect process threads under this executor, so that part was disabled.
The game adapter still requires a Windows build and in-game validation.
