# ChainMorningstarVR — audited baseline

This is the independent ChainMorningstarVR project. Do not mix historical
symptoms or assets from the earlier ChainedMorningstarVR implementation into its
runtime evidence. User-provided unmodified vanilla records in ReferenceBundle
are primary inputs, not an older mod implementation.

Audited main: `0777e257d64fcab908df03ff94e7a9af4ff1a0ee` (2026-10-06).
Current work: `astra/zero-base-audit-v050`, 0.5.0 audit preview.

## Requirements

Skyrim VR; one-hand mace; damage44, weight17, value550; Eorlund sale; faithful
reference appearance; physical chain with chain sounds; head/spike actual
contact damage; enemy head/weapon contact drops the corresponding equipment
with 1/3 probability per distinct impact.

## Current geometry contract

- Handle56cm; 14 links; first-to-last link-centre span84cm.
- Iron core diameter32cm; spike tips at radius24cm.
- Head centre straight reach from anchor106.5cm.
- Fourteen spike directions shared by mesh/core; 24cm envelope is broadphase,
  never a substitute for actual narrowphase shape.
- These are authored dimensions retained from the audited source. The supplied
  image has no physical scale ruler, so exact real-world scale cannot be derived
  from it alone. In-game size still requires user visual verification.

## Evidence boundaries

Earlier CI passes establish only earlier commits' build status. Earlier target
logs mentioned in the handoff were not attached in this turn and are not proof
of this build's runtime behavior. No new Windows DLL or in-game pass is claimed.
Local portable core tests, source-schema audit and generated asset checks are
recorded separately from runtime gates.

The former native-proxy-test mode is removed. A plausible read-only layout or
PLANCK version cannot authorize native writes. See NATIVE_BRIDGE_AUDIT_20261006.md
for the replacement design and unsolved collision adapter requirements.
