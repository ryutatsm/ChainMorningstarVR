# Release gate — audited development branch

All gates are required. A compiler pass, NIF parser pass, or simulated test does
not establish in-game compatibility. Do not reuse evidence from the old
ChainedMorningstarVR project or a different build combination.

## Build provenance

- Pin source commit and external dependency revisions.
- Windows Skyrim VR DLL build succeeds for the actual source delivered.
- Plugin binary structural tests pass; xEdit Check for Errors passes.
- WEAP local 00000800 and first-person STAT local 00000801 share custom model.
- Mace / damage44 / weight17 / value550 and vanilla sound/impact/equip data verified.
- Final NIF node tree, actual transforms, triangle bounds, 7 texture references,
  DDS format, mip count, normal alpha and shader flags verified.
- Package contains one matched DLL/ESP/NIF/DDS set with SHA-256 manifest.

## In-game appearance and lifecycle

- Record runtime, SKSEVR, HIGGS, PLANCK, VRIK versions actually used.
- Eorlund sells weapon; purchase, buy-back and stock reset work on new and existing saves.
- Right/left single-hand equip displays the reference design and correct scale.
- Chains, collar, wood, leather, plaque and metal surface judged in VR lighting.
- Sounds audible, spatially correct, no stuck sound on sheathe/unequip/load.
- Pause/resume, tracking discontinuity, cell/fast-travel and save/load stable.
- Repeated equip/unequip and at least 10 minutes of combat produce no CTD or detached bodies.

## Physical combat

- Actual head compound aligns with core and spike surfaces at every simulated pose.
- Each link and head have justified physical world contacts; no wall penetration.
- Contact feedback stops/rebounds the simulated head, not merely its rendered mesh.
- Test both fast sweep and tip-only contacts; empty gaps between spikes do not hit.
- No stale handle/steel-mace-position damage or duplicated native + custom damage.
- Native block, armor, perks, stagger, kill credit, hostility and crime behavior preserved.
- Callback threading, world lock, body ownership and restore lifecycle verified.

## Equipment drop

- Actual enemy head surface contact resolves the worn helmet/headgear instance.
- Actual enemy weapon surface contact resolves that hand's equipped weapon instance.
- A hand/torso hit never substitutes for a weapon/head hit.
- Every eligible distinct contact episode gets one unbiased 1/3 draw; resting or repeated
  callbacks do not reroll. This is probabilistic, not exactly every third hit.
- Only the struck equipment drops. Tempering/enchantment and exact instance retained.
- Teammates/player, protected quest items and invalid/stale instances are excluded.
- Empty/unarmed/nonhumanoid targets handled without invented equipment.
- Fatal hits and dead-actor policy explicitly implemented/tested; current foundation
  rejects dead actors, which must be revisited if queued contact follows a killing blow.
- New game/load/equip generations invalidate pending contacts; no dangling pointers.

Only after all gates pass may a completed release archive be offered.
