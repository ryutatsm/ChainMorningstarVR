# 0.6.1 equipped attachment repair

The 2026-10-06 18:44 feedback bundle loads CMS 0.6.0, SKSEVR 2.0.12,
HIGGS 1.10.10 and PLANCK 0.8.1 with VRIK 0.8.7. CMS logs neither scene
acquisition nor native head preparation/attachment. The screenshot and user
report show the straight authored model at the player's feet, unaffected by
hand movement. This establishes that loading the DLL was not enough; it does
not establish whether the former update hook ran.

## Confirmed defects and repairs

1. The exported BSFadeNode lacked `NiStringExtraData Prn=WeaponMace`.
   Both ironmace.nif and steelmace.nif in the user's private reference bundle
   have this exact root metadata. Add it; keep mesh vertices, UVs, materials,
   texture images, emblem, local transforms and scale unchanged. Preserve
   vanilla dynamic/articulated Havok flags plus transform updates for the chain.
2. Acquisition searched `Right/LeftMeleeWeaponOffsetNode`. HIGGS explicitly
   separates these collision offsets from its visible weapon lookup. Select
   `WEAPON`/`SHIELD` in the first-person skeleton, or the third-person skeleton
   when VRIK is loaded. Prove the exact CMS form is equipped, then retain the
   private anchor and its direct model parent (the engine may rename the root).
   Recheck live skeleton, slot, anchor, equipped form, cell and handedness.
3. The sole collision object was on `CMS_HeadNode`. Vanilla references put it
   on the weapon root, and HIGGS `GetRigidBody` does not search children. Move
   the same 15 hulls to a root `bhkRigidBodyT`, offset/rotated to the authored
   head pose. Clone its head-local shape for the native backend. The visual
   head no longer owns a competing body. Runtime collider uses simulated pose.
4. Replace the independent player vtable patch with HIGGS's documented
   post-VRIK/post-HIGGS callback. Read the game's frame delta after tracked
   hand transforms update. Add callback, acquisition and bounded movement /
   native-readiness diagnostics. Preserve the fixed 90 Hz chain solver.

Physical left/right HIGGS bodies and logical equipment slots are distinguished
using SKSEVR's left-handed-mode flag, also used by HIGGS. No player collision
pointer writes were introduced. Only one CMS at a time remains supported.

## Source evidence

- HIGGS commit `93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee`:
  `src/hand.cpp` (`GetWeaponNode`, `CreateWeaponCollision`, `PostVrikUpdate`),
  `src/hooks.cpp` (`PostVRIKPCUpdateHook`), `src/utils.cpp` (`GetRigidBody`,
  `GetRigidBodyTLocalTransform`), `src/RE/offsets.cpp` (`g_deltaTime=0x1EC8278`).
- SKSEVR mirror `Odie/sksevr-mirror`, commit
  `7ed497e87dc66935d6b6fbcc70a09ba2287307ad`, `skse64/GameInput.cpp`:
  `g_leftHandedMode=0x1E71778`. Both reads are guarded by the existing strict
  SkyrimVR 1.4.15.0 load check.
- Private reference NIFs are used for inspection only and are not distributed.

## Verification and target test

Exporter roundtrip requires exactly one root Prn, the correct value, root
collision ownership, transformed body, correct authored head offset, no head
body, and all 15 convex hulls. Portable scene tests reject offset-node decoys,
wrong skeleton/hand, detached old graphs and accept renamed equipped roots.
Windows compilation and matching-commit packaging remain release gates.

This repair has not been run in Skyrim VR here. In game, re-equip and draw,
move only the arm for 15 seconds, then touch the iron ball to a wall/floor.
Check `CMS frame callback alive`, `acquired`, `Native head prepared`,
`Native head attached` and `CMS tracking sample`. A callback alone does not
prove physics, and a build pass does not prove combat or stability.

The existing limits remain: individual chain links have no world colliders;
unsupported NPC weapon geometry is skipped; equipment drop is one independent
1/3 draw per certified head/weapon contact episode. Test combat after tracking
and ball collision work. The repaired feedback launcher from c621a2a is retained.
