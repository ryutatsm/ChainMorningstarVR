# 1.0.0-rc2 — offhand selection conflict fix

The user equipped CMS in the right hand and could not grab the ball with the
left. The received `CMS-feedback-20261007-005251.zip` actually loaded rc1.
Its sampled log has two rejected attempts with `reason=higgs-two-handing`,
`captured=false` and palm-to-ball distances 0.15198505 m and 0.22051072 m.
The first is within the existing scaled capture radius. There are no held
entries. This is an observed failure, not merely absent test evidence.
Only aggregate evidence and hashes are published; user logs remain private.

## Cause and change

Pinned HIGGS `Hand::FindCloseObject`/`FindOtherWeapon` uses a selection sphere
with filter info exactly `0x2C` (CustomPick2). It finds the HIGGS weapon body
that CMS has moved to the ball. Its state becomes SelectedTwoHand, which
`CanGrabObject` excludes. CMS cannot arm its grip while that state is selected;
the unsuppressed grip then lets HIGGS enter HeldTwoHanded. The rc1 busy guard
correctly rejects the already-owned hand but cannot prevent this cycle.

Rc2 registers a public HIGGS collision-filter comparison callback and brackets
HIGGS Update with its public pre/post callbacks. Only on that calling thread,
and only while a certified right-hand CMS body is active and the left equipment
slot is empty, the exact CustomPick2 sphere ignores the right-hand CMS filter
signature. HIGGS therefore cannot select CMS as the other weapon. The existing
CMS priority-65 grip capture runs before HIGGS priority 66 and can own the press.

The callback receives filter integers, not body pointers. HIGGS assigns the same
signature to the right hand and its weapon, so it also excludes the right
HIGGS hand from these selection queries; that hand is not a grabbable reference.
The scope is not opened if either HIGGS hand already holds an object, preventing
unintended filtering of held objects sharing that signature. Player group and
part bits must match; foreign objects and NPC groups do not match.

Actual contact comparisons (wall/floor/NPC/physical hand layers) return Continue.
No filter integer, global HIGGS layer mask, setting, weapon form or INI is edited.
Other threads and all comparisons outside HIGGS Update return Continue.
The callback uses only thread-local scalar values, with no engine reads, locks
or allocations. The game-thread bracket checks current equipped form, pause,
draw state, hand ownership, current HIGGS body, shape, world and pose freshness.
Normal disabled/holding/pulling guards are retained. No synthetic grip or forced
release of another mod's held object is introduced.

## Validation and target check

`Tests/offhand_selection_ci.cpp` reproduces the rc1 state-ordering failure in a
small fixture derived from HIGGS source, then checks that selection exclusion
allows the same in-range press to hold and release the ball. It checks both
filter argument orders, wrong groups/parts, exact query identity, disabled-bit
transitions, end-of-scope restoration and every other layer 0–127.
It is a contract simulation, not execution of Skyrim or HIGGS binaries.
The existing physics/drop/input tests and matched Windows build gates still apply.

After updating, restart Skyrim VR, equip CMS in the right hand, empty the left,
release grip, approach the ball and briefly stop, then press/hold grip. Check
hold, release, overextension and menu/unequip reset. Check ball-to-floor/wall
contacts and switch to an ordinary sword to check normal HIGGS two-handing.
Logs record `CMS offhand selection guard: rejectedPickPairs=...` for intercepted
selection comparisons and `CMS offhand head grip: held/released` for actual holds.
An already-held HIGGS two-hand state requires button release; CMS does not seize it.

The rc2 target retest is pending. Equipment-drop references were absent in rc1
and its two sampled certified head contacts were ineligible. General release
gates remain in `Docs/RELEASE_GATE_NEW_BUILD.md`; this candidate does not claim
all gates passed. Appearance, dimensions, impact audio, blood, equipment policy
and physical collision response are unchanged from rc1.

## Primary source audit

- HIGGS 93bf67b: `src/hand.cpp` (FindCloseObject, FindOtherWeapon, Update,
  IsInGrabbableState, ControllerStateUpdate and filter construction),
  `src/hooks.cpp` (PlayerCharacterUpdateHook, CompareFilterInfo hook),
  `src/pluginapi.cpp` and `include/higgsinterface001.h` (public callbacks).
  https://github.com/adamhynek/higgs/tree/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee
- PLANCK f06fc95: `src/main.cpp` CollisionFilterComparisonCallback returns
  Continue for the CustomPick2/HIGGS pair; its character-controller and biped
  policies do not force a selection hit ahead of the CMS callback.
  https://github.com/adamhynek/activeragdoll/tree/f06fc953334aeea912975af6302e52e1bad92b01
