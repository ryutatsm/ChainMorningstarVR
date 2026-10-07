# 1.0.0-audit3: head pose and contact stability

Runtime diagnostic; not a completed release. User-authorized work branch and
Windows/Vortex delivery. Physical VR confirmation is still required.

## Evidence

Input: `CMS-feedback-20261007-102609.zip`, SHA256
`7663a41756b444b54d3e9cf1cab3f66bac09a3edc79e43444c97d963c8b2f4ef`.
Audit2 logged five trigger holds, four voluntary releases and one obstruction
release. Longest recorded hold: 29,962 ms. One hold reached 0.298 m target error;
two later attempts had 0.548/0.497 m native/visual centre separation. The user
reports involuntary rotation/motion while held and violent floor bounce.
The old logs have no angular or native-warp telemetry, so they cannot identify
every observed bounce's cause.

## Confirmed code defects and changes

1. Rebuilding `basisFromLocalZ` at every render/physics update changed its
   reference axis at `abs(z.z)==0.90`. A direction change of about 0.00046 rad
   produces a 1.5708 rad roll. Head and links now retain and parallel-transport
   their orientations. Free head alignment is limited to 6 rad/s and suspended
   while supported, so a settling end-link cannot rotate spikes into the floor.
2. The grab saved only palm-relative translation. It now saves full rotation
   too; the same explicit rotation reaches visuals, native collision and the
   compound helper. Release resumes bounded alignment without an orientation
   snap. Position contact/reach constraints remain authoritative.
3. Fixed-step contact projection moved position without previous position,
   turning recovery into Verlet velocity. Projection now translates both.
   The separate callback correction was removed to avoid applying it twice.
   Restitution/friction, mass, link collision and impact sound gates are retained.
4. Native code assumed HIGGS changed only keyframe velocity. Pinned HIGGS
   `93bf67b`, `hand.cpp:MoveHandAndWeaponCollision` calls
   `physics.cpp:ApplyHardKeyframeVelocityClamped`, which can set position and
   rotation when velocity limits are exceeded. Before casting, CMS restores
   its prior commanded endpoint if the same certified body has been displaced
   or turned. History clears on detach/world/body/lifecycle changes. This is a
   plausible contributor to the recorded native lag, not proven from audit2
   logs alone. New sampled diagnostics record restoration and sweep magnitudes.
5. The currently holding HIGGS left hand is excluded from CMS head contact
   feedback, avoiding a grasping finger becoming an expulsion plane. Other
   objects/NPCs and non-damaging VRIK chain contacts remain enabled. No global
   HIGGS settings, physical filter bits or PlayerCharacter collision fields
   are changed.

## Verification and limits

Portable tests exercise the 90-degree regression, full palm-relative pose at
45/50/72/80/90/120/144 Hz, floor rest, blocked-grip release, and native endpoint
history. Existing tests cover 21 input/scale/rate combinations, taut chain,
collision response, sound and equipment-drop policy. Windows CI compiles the
actual DLL and builds matching assets. The package verifies complete source
manifests and exact binary hashes against the recorded source commit.

These tests do not execute Havok, HIGGS, VRIK or real tracked controllers. Native
endpoint restoration assumes a keyframed body has advanced to its prior target;
the new diagnostics are needed to verify scheduling on the user's installation.
Do not certify stability, damage/drop integration or completion from CI alone.
Approved geometry/materials, 19 links, Japanese naming and trigger input remain.
See `DIAGNOSTIC_TEST_AUDIT3_JA.txt` for the short physical test.
