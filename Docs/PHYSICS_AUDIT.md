# Physics and runtime audit — 2026-10-06

Baseline: `main` commit `0777e257` (audited from source, not from the prior handoff's completion claims).

## Decision

Keep the dependency-free mass-weighted particle solver as a **visual chain simulation**, fixed-step clock, scene transform utilities, and geometry contracts. Keep diagnostic native-layout reads separate from any mutation authority.

Do not treat the solver or the former native `collisionNode` pointer replacement as a completed physical flail. The current core only projects particle distance constraints. It has no terrain/actor contacts, chain-link collision, angular rigid-body constraints, contact impulses, or feedback from Havok. The head orientation follows the final segment rather than an independently rotating rigid body. `consumeWorldContactImpulse()` currently returns zero. This does **not** fulfill the requested fully physical chain or actual iron-ball damage. Native integration is a release blocker.

The former pointer-write path has been removed in the accompanying native bridge audit. A plausible `VRMeleeData` layout or successful pointer assignment never established Havok world membership, filters, contact callbacks, correct damage, or ownership by PLANCK/HIGGS.

## Reproduced defects and changes

| Finding in baseline | Evidence | Change |
|---|---|---|
| Sphere segment query reported hits past the actual endpoint | Sweep `(0,0,0)` → `(1,0,0)`, radii `0.1`, target center `(4,0,0)` incorrectly returned a hit at `t=1` | Reject intersection times outside `[0,1]`; preserve endpoint, tangent, and initial-overlap contacts |
| Fixed-step clock depended on render rate | Two seconds produced **179** simulation steps at 72/80/144 Hz, **180** at 45/90/120 Hz | Double-precision clock arithmetic; all six rates now produce 180 steps |
| Nonfinite tracking/time could poison persistent state | NaN frame time or invalid anchor reached simulation arithmetic | Reject invalid samples; invalid controller sample clears its pending sweep |
| Compound support overstated spikes | Formula added a cone's base radius at its tip | Support is the maximum of the base disk and tip projections; it is not a ray-surface intersection |
| Failed reacquisition retained nodes / could preserve old active state | Re-equip after successful acquisition, followed by failed anchor read | Release previous ownership before reacquire, clean up every acquisition failure, only activate an equipped controller |
| Zero-time updates could submit motion work | Driver forwarded paused frames | Skip nonpositive/nonfinite time after checking scene ownership |
| Rattle gate compared first link with a stationary origin | First relative velocity started at zero | Compare first link with anchor velocity |

Teleport relocation produces a zero-length, zero-speed sweep. The head geometry contract now agrees with the reference model: 16 cm core, 24 cm spike tips, 14 spikes; eight rim spikes offset by 22.5 degrees and three on each face. This leaves the central plaque and chain socket clear. The non-damaging attachment eye extends beyond the 24 cm damage broadphase.

## Measurements and verification

Command:

```sh
g++ -std=c++23 -O2 -Wall -Wextra -Werror -pedantic -I. Tests/physics_core_ci.cpp -o /tmp/cms_core_tests
/tmp/cms_core_tests
```

Result: **PASS**. Regression coverage includes all six render rates, sphere hit/miss boundaries, invalid samples and recovery, teleport sweep suppression, failed/partial reacquisition, scene loss during pause, spike support, and diagnostic timer validation (negative cooldown valid; NaN/infinite timers invalid).

Measured default straight reach: `1.065 m`. Static gravity settling maximum distance-constraint error: `0.00131541 m`. Difference between 45/90 Hz head positions for the same 0.45 m / 0.2 s linear anchor path: `5.58794e-09 m` after the clock change.

An additional baseline stress measurement with one second of constant 20 m/s anchor motion produced maximum local constraint error `0.0456352 m` (10 m/s: `0.0155058 m`). This demonstrates finite-iteration stretch, not a measured in-game behavior or a passed realistic-swing requirement. No stiffness/world-contact solution is claimed here.

## Remaining integration risks

- `ChainController::headSweep()` compresses up to five fixed steps into one straight chord. A curved path can cross a target while that chord misses. A future contact backend must consume substep motion, not just frame endpoints.
- The 24 cm sphere is a broadphase envelope. Using it directly as damage geometry would hit empty space between spikes. Damage needs the true core/spike narrowphase.
- The particle chain has no torsion or rigid-ring interlocking model; visual ring orientations are constructed from tangents.
- Nonunit scene-root scale is accepted by the preview bridge. Future physical shapes, displayed mesh size, and solver lengths must share the same scale convention.
- C++ tests do not execute Skyrim VR, Havok, HIGGS, PLANCK, native sound playback, equip/load lifecycles, or equipment drops. Runtime validation is still required before a gameplay release.
