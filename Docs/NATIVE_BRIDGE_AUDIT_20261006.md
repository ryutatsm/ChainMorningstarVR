# Native bridge audit — 2026-10-06

Audited baseline: `0777e257` on `main`. This is source analysis, not a Skyrim VR runtime pass.

## Decision

Keep the scene graph bridge, fixed-step chain simulation, and read-only VRMeleeData diagnostics after the lifecycle corrections below. Remove the opt-in PlayerCharacter `collisionNode` mutation path. Do not label the remaining visual chain as a complete physical flail.

## Findings and corrections

- `updateNativeMeleeHeadProxy` never used the supplied head sweep to move a physics body. The native write branch only replaced a NiPointer at PlayerCharacter + `0x710/0x7E0 + 0x18`; it did not demonstrate the final HIGGS body transform, collision shape, actor hit source, or contact feedback.
- The previous player-address comparison could not detect the same PlayerCharacter object surviving a cell/world change or a save/load. Removal avoids restoring a stale collision node into a reconstructed melee state.
- The exact HIGGS source provides a possible reason a swapped node could affect collision: HIGGS clones its shape and tracks shape identity. Thus it is **not** correct to conclude that a node swap can never affect the collision. The unsupported inference was that swapping the node proves a correctly sized articulated head collider.
- Native writes and the write-layout alias were removed. Defining the retired `CMS_ENABLE_NATIVE_MELEE_PROXY=1` now causes a compiler error. The original write experiment remains in Git history.
- Optional native reads use a byte-copy snapshot and are limited to Skyrim VR 1.4.15. Scalar plausibility is explicitly not pointer, object-type, or lifetime validation. Nonfinite diagnostic timers are rejected without rejecting legitimate negative cooldowns.
- The visual bridge reacquires after player/cell changes, sheathing, detached graph ownership, or pause/resume. It checks that all animated nodes are direct children of the chain anchor, validates finite input poses, and immediately updates the owned subtree after changing local transforms.
- Pre-load shutdown suspends automatic reacquisition until a post-load/new-game request. Sound handles and NiPointer references are cleared even after partial acquisition.
- The update hook is idempotent and rejects nonfinite delta time. The VR vtable slot `0xAF` agrees with HIGGS' own PlayerCharacter update hook.
- Four bounded native one-shot sound handles replace empty rattle/clank methods. Skyrim.esm `SNDR:0003D128` (`PHYChainSD`) was checked against the user-supplied record; it selects among four vanilla physics-chain samples. Handles follow the head and stop on release. No Bethesda sound files are redistributed. This source implementation still needs an audible in-game check.

`consumeWorldContactImpulse()` remains explicitly empty because this build has no certified native contact source. Consequently the impact-clank path does not falsely manufacture a contact.

## Primary source references inspected

1. HIGGS commit `93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee`:
   - [`src/hand.cpp`](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hand.cpp), `ComputeWeaponCollisionTransform`, `CreateWeaponCollision`, `UpdateWeaponCollision`, `MoveHandAndWeaponCollision`.
   - [`include/higgsinterface001.h`](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/include/higgsinterface001.h): `GetWeaponRigidBody`, `AddPrePhysicsStepCallback`, and collision callback signature.
   - [`src/hooks.cpp`](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hooks.cpp): prephysics callback timing and update hook slot.
   - [`src/physics.cpp`](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/physics.cpp): collision recognition by exact hand/weapon/held-body identity.
2. PLANCK commit `f06fc953334aeea912975af6302e52e1bad92b01`:
   - [`src/main.cpp`](https://github.com/adamhynek/activeragdoll/blob/f06fc953334aeea912975af6302e52e1bad92b01/src/main.cpp): `IsHiggsRigidBody`, contact listener, and actual hit dispatch.
   - [`include/RE/misc.h`](https://github.com/adamhynek/activeragdoll/blob/f06fc953334aeea912975af6302e52e1bad92b01/include/RE/misc.h): `VRMeleeData` layout and negative cooldown semantics.
3. CommonLibSSE-NG public declarations and implementations for `BSAudioManager`, `BSSoundHandle`, `NiAVObject`, `hkpRigidBody`, and `hkpContactListener`; the project pins the actual compile dependency separately.
4. User-supplied `ReferenceBundle.zip`: `SNDR_0003D128.record`; record data inspected privately and not added to the repository.

## Workable next physical backend

Prefer an adapter around the **existing HIGGS weapon rigid body**, retrieved through the published API, over writing vanilla PlayerCharacter internals. PLANCK already identifies that body as the player's weapon. The adapter requires all of the following before enabling gameplay:

1. Install the head-only 15-piece compound on that body while preserving and verifying its prior shape. HIGGS clones and rescales the original weapon collision; its melee-scale undo, VRIK hand scale, and weaponCollisionScale must be accounted for. A constant Skyrim-unit conversion alone is insufficient.
2. Drive that body at the simulated head pose after HIGGS/VRIK's weapon pose writes and before Havok steps. With VRIK enabled, `ComputeWeaponCollisionTransform` replaces the body transform with a hand-relative transform, so merely updating CMS_HeadNode cannot prove the final collider position. The published prephysics callback is an appropriate synchronization point to investigate.
3. Register a verified contact listener on the exact owned HIGGS body. The public HIGGS collision callback supplies hand/mass/separating velocity, but no other body or point; it is insufficient to certify enemy head versus equipped weapon contact or to resolve world penetration.
4. Feed actual contact position, normal, and relative velocity into the chain solver. A keyframed body driven through a wall without this feedback is still not a physical chain. Avoid solving one observed contact repeatedly across solver iterations.
5. Certify own attacking-body identity and the actual target node/weapon instance. Route one contact episode, separated by actual disengagement, into the equipment-drop service on the game thread. Ordinary TESHitEvent proximity is insufficient.
   The inspected PLANCK source's enemy-weapon-body activation code is inside a block comment (`src/main.cpp`, approximately lines 5464–5524, with an offhand TODO). Therefore the adapter must additionally provide or verify enemy weapon colliders, or use exact swept weapon-mesh geometry. A hand hit must not be reclassified as a weapon hit.
6. Own a world/equipment generation, restore only a body/shape still owned by the adapter, clear contact queues across load/unequip/cell transitions, and never dereference collision-thread pointers from a later main-thread task.

Minimum blocker is the native adapter in steps 1–4, including target-machine verification of transform scale, thread timing, lifetime, and real contact feedback. Public source availability alone does not establish those runtime properties. Neither the visual solver tests nor a successful Windows DLL link can substitute for them.

## Remaining limits

Only one acquired weapon instance is animated at a time; right hand is selected first if both hands contain this weapon. Nonunit scene scale is rendered, but chain lengths and future collision dimensions still require an explicit physical scaling policy. No runtime claim is made for 90 Hz performance, full-world contacts, true head damage, or equipment drops until a real collider adapter is installed and validated in Skyrim VR.
