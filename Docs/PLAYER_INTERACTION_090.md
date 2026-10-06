# 0.9.0: upright inventory, Japanese name, offhand ball hold, player-body contacts

The user reported 0.8.1 working. `CMS-feedback-20261006-220214.zip`
records nine sampled impacts, each accepting both sound layers at build,
position, volume and play stages. It also attaches the 15-hull native head and
19 links. No CMS warning/error is present. Audio and existing weapon behavior
are retained. The new 0.9.0 interactions still require an in-game test.

## Display

The unlocalized ESP's FULL is UTF-8 `チェーンドモーニングスター` with a terminating
NUL. Local FormIDs 800/801, 44 damage, 17 weight, 550 value and vendor injection
are unchanged. The source builder and xEdit scripts agree. No vanilla overrides.

A root `BSInvMarker` named INV has rotation (4712,0,0) milliradians and zoom 1.
Inventory angles are clockwise: -4.712 about X maps the authored +Y long axis
to screen +Z, placing the ball above the handle. This changes only menu extra
data, not vertex/node transforms, collision, Prn or equipped placement. Nifly
roundtrip checks the marker and the existing 15 hulls/19 links/blood pair.

## Physical left grip on the right-hand weapon

An SKSEVR controller callback at priority 65 runs before HIGGS's priority 66.
It records raw grip state and claims a fresh press only when the game-thread
bridge has armed it near the ball, with an empty, available physical left hand.
The claimed grip's press/touch bits are suppressed before HIGGS sees them; other
buttons and other controller inputs are unchanged. This prevents HIGGS from
starting its rigid two-handing pose or grabbing a nearby item at the same time.
No `GrabObject(player)` call or fabricated world reference is involved.

Input snapshots and arming expire after 150 ms. Atomics exchange only scalar
state between callbacks and the game thread. The physical left device is read
using SKSEVR's documented BSOpenVR `GetTrackedDeviceHand(left=0)` slot 0x0D;
`g_openVR` is at 0x2FEB9B0 for the plugin's guarded VR 1.4.15 executable.
The interface version/source ABI and controller-state size are checked.

The palm is approximated between the wrist and middle-finger base of the
current visible skeleton. Capture preserves the ball-to-palm offset. A second
solver endpoint is interpolated at 90 Hz; all 19 links remain simulated between
the weapon anchor and held ball. Native world contact takes precedence over the
hand target. Releasing the grip restores gravity and bounded motion (held-head
speed capped at 8 m/s). Overextension, a tracking jump, an occupied hand or a
large hand/ball separation releases the hold. Another press requires releasing
the grip first. The retained grip is consumed until release to avoid an
accidental HIGGS mid-press grab after an overextension.

Unequip, pause, loading, skeleton replacement and teleport follow the existing
owner-release path, clearing grip capture, hold state and body samples. Left-hand
weapon use still works; holding its head with the right hand and dual copies are
outside this requested interaction. No finger-pose override or VRIK setting is
installed. The input still requires a physical grip press.

## Chain against the user's VRIK body

Eleven query-only anatomical capsules track pelvis/spine, neck/head, both upper
arms/forearms and thighs/calves on the current VRIK skeleton. Dimensions use the
visible bone world scale. There are no inserted bodies, new Havok listeners,
PlayerCharacter collisionNode writes, filter changes, player impulses, damage
or equipment drops from these contacts.

Each link has a relative sweep against the moving capsule segments. Swept AABBs
reject distant pairs, then bounded conservative advancement finds contact;
static overlap is also handled. Contacts feed the existing chain-only plane
solver. The body's frame motion is swept once; subsequent fixed-step/constraint
queries use its current position. Samples refresh every frame and are discarded
across ownership loss or large tracking jumps. Body velocities are bounded.
First three contact batches and first twelve grip transitions per equip are
logged, plus counts in the existing tracking samples.

These are anatomical approximations, not exact clothing/armor collision or
link-to-link collision. Body contact requires the visible VRIK skeleton. Chain
contact remains one-way and cannot physically move the user's controllers or
body. Conflicting wall/body/length constraints can still stretch the chain.

## Verification and sources

- New portable test: offset-preserving capture, release/repress, occupied hand,
  no remote pull, tracking jumps, 45–144 Hz held endpoints, gravity after release,
  wall priority, full body crossings, overlap, moving body and invalid samples.
- Existing portable collision/contact/damage policy tests and ESP binary tests.
- Local NIF compile/roundtrip: 22 nodes, 34 shapes, 15 hulls, 19 links, native blood
  pair and INV marker. Source/asset pairing and Windows DLL are build gates.
- Target checks: inventory name/orientation; hold/move/release with left grip;
  chain against torso/arms/thighs; release across menus/load/unequip; normal
  HIGGS grabs away from the ball. A successful build is not a runtime pass.

Primary ABI sources inspected:
- [SKSEVR PluginAPI.h](https://github.com/Odie/sksevr-mirror/blob/7ed497e87dc66935d6b6fbcc70a09ba2287307ad/skse64/PluginAPI.h),
  GameVR.h/.cpp, openvr_1_0_12.h, InternalVR.h/.cpp and Hooks_VR.cpp at the same commit.
- [HIGGS main.cpp](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/main.cpp),
  ControllerStateCB, registration priority 66 and physical hand-role mapping;
  hand.cpp input arbitration and the bundled interface001.
- [Nifly ExtraData.hpp](https://github.com/ousnius/nifly/blob/cca0a770094bb962fb28ea1fec5ea903e68fda8e/include/ExtraData.hpp),
  BSInvMarker; [Beyond Skyrim NIF data format](https://wiki.beyondskyrim.org/wiki/Arcane_University%3ANIF_Data_Format)
  for clockwise inventory rotations and the INV convention.
