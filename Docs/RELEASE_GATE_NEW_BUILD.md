# ChainMorningstarVR — release gate for the NEW build

A release archive must pass all checks below on the target Skyrim VR installation.

## Build identity
- Every binary/model/record is produced from this repository.
- No NIF/ESP/DLL from an earlier morning-star project is included or used as a template.
- CI source commit and SHA-256 hashes are recorded.

## Weapon record
- One-handed mace classification.
- Damage 44.
- Weight 17.
- Value 550.

## Visual/NIF
- Correct ~2x blueprint scale.
- 56 cm handle.
- 14 chain link runtime nodes.
- 84 cm first-to-last link-centre span.
- 32 cm iron core and 8 cm spikes.
- CMS_ChainAnchor, CMS_LinkNode_00..13, CMS_HeadNode survive NIF round-trip.
- Metal diffuse/normal/specular/environment maps resolve and no purple textures.
- Iron ball reads as rough forged steel, not smooth plastic.

## Physics/runtime
- Fixed 90 Hz chain simulation remains stable under common VR frame rates.
- Head centre maximum straight reach from anchor is 106.5 cm.
- Visual head and collision proxy remain coincident during extension, lateral swing,
  return swing and rapid direction changes.
- Handle and chain do not produce the head's 44-damage hit.
- Gaps between spikes are not treated as a fully solid 24 cm sphere.
- All 14 visible spike directions are represented by narrow-phase collision.
- Each valid contact produces one native hit/damage event, not duplicates.
- Native blocking/perks/stagger/hostility/kill credit remain intact.

## Stability
- Right-hand and left-hand equip paths both work.
- 50 equip/unequip cycles without CTD.
- Save/load, death/reload, fast travel and cell transition without stale-node CTD.
- Ten-minute combat stress test without progressive frame-time loss or leaked nodes.
- Vortex install/deploy/purge/redeploy leaves no orphan files.

## Evidence rule
A regression check is added only when the problem is reproduced by THIS repository.
Do not add release criteria merely because an older, separate morning-star project once
exhibited a similar symptom.
