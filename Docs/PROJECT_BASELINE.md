# ChainMorningstarVR — clean-room project baseline

This repository is the NEW Chain Morningstar VR implementation.

## Isolation rule

Do not use implementation details, NIFs, ESPs, collision placement, hit results, Papyrus/SKSE
logs, or bug symptoms from any previously-created chain morning star / morning star mod as
evidence for this project.

Historical failures from another weapon build are not regression cases here unless they are
reproduced independently by this repository on the target Skyrim VR installation.

## Authoritative design for this project

- Target: Skyrim VR.
- One-handed mace.
- Damage 44.
- Weight 17.
- Value 550.
- Approximately 2x the supplied blueprint dimensions.
- Handle: 56 cm.
- Chain first-to-last link centre span: 84 cm.
- Iron-ball core: 32 cm diameter.
- Spikes: 8 cm.
- Runtime chain: 14 links, fixed 90 Hz simulation.
- Head centre straight reach from chain anchor: 106.5 cm.
- Head hit geometry: 16 cm core + 14 spike proxies; 24 cm sphere is broadphase only.
- Realistic forged-steel surface with authored normal/specular/environment response.

## Runtime evidence accepted so far

Only evidence collected from this clean-room repository counts.

- Windows/MSVC CommonLibSSE-NG VR release and read-only diagnostic DLLs compile in CI.
- Target runtime log detected PLANCK API revision 1, build 80100.
- Read-only VRMeleeData candidates are present for both hands at the PLANCK-published
  PlayerCharacter offsets. Their world/collision pointers and scalar/flag fields are
  structurally plausible.
- Equality between VRMeleeData.offsetNode and CommonLib's named MeleeWeaponOffsetNode is NOT
  a validity requirement. PLANCK's published structure does not document that identity.

No native VRMeleeData writes are enabled yet.
