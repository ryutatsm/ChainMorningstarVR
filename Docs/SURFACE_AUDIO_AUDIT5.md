# Audit5 — sustained floor friction, motion audio and resilient feedback

The user reports that audit4 equipment drops work. No audit4 feedback ZIP was
available, so this is user observation without log verification. They report
almost frictionless floor sliding and request iron scrape, air-cut and
successful-disarm sounds. These are the scope of audit5.

## Floor response

The existing callback friction was proportional to inward normal velocity.
Fixed-step contact projection had already removed that velocity at rest, so
subsequent horizontal motion received no sustained friction. Changing the
Havok material alone cannot fix the independently integrated CMS head.

The 90 Hz solver now applies a gravity-supported Coulomb displacement budget
once per fixed step: static coefficient 0.80, kinetic 0.55. It uses the most
supportive actual contact plane and velocity relative to that surface, rather
than multiplying resistance by manifold point count. The corrected head stays
coupled to the chain. Holding bypasses this resistance; air motion is unchanged.
Expired contacts cannot pin the head. Impact restitution remains unchanged.

Portable tests reproduce 0.173385 m of drift in a three-second slack-chain
scenario without the fix, and 0 m with it. Deliberate taut pulling still moves
the head. Horizontal moving support carries it; unsupported free swing matches
the old solver. Held motion, contact expiry and existing multi-rate resting,
grab and collision suites pass. This is not a measured VR friction result.

## Original sound assets and lifetime

`Source/Audio/generate_audio.py` synthesizes three mono PCM16 44.1 kHz WAVs.
Scrape and air are periodic two-second textures; disarm is a 0.85-second low
metal transient. No external recording or Bethesda sound file is redistributed.
Peak, RMS, DC, loop boundary, file format and hashes are checked when generated.

New local SNDR forms 802/803/804 use the verified user-exported PHYChainSD
standard-descriptor metadata (source record version 40). Its sound category and
spatial output model remain native; sample paths, playback characteristics and
loop flags are authored for CMS. Weapon 800 and first-person model 801 remain
stable. `BGSStandardSoundDef::LengthCharacteristics` in pinned CommonLib 3.5.2
documents the 0x08 whole-file loop bit in LNAM byte 1. Synthetic independent
binary-reader tests verify record IDs, group counts, paths and loop modes.

The game-thread audio service uses the same `BuildSoundDataFromDescriptor`,
`SetPosition`, `SetObjectToFollow`, `SetVolume`, `Play` and `Stop` APIs as the
already audible CMS impact/chain sound path. Scrape gain follows supported
surface-relative sliding speed. Air gain follows head speed relative to the
anchor, excluding contact and held states. Smoothed gains avoid abrupt clicks.
Stationary contact and uniform player translation do not start these effects.

The disarm cue is requested only after `RemoveItem(kDropping)` returns a real
dropped reference. A lottery loss, rejected instance or missing reference is
silent on this path. Four drop handles decay independently. Loop and drop
handles stop on the existing unequip/pause/load/teleport teardown. No audio
request changes combat damage or triggers an additional lottery.

## Feedback collector

The user's exact failure is unknown without its error screen. The previous
collector could abort before creating a ZIP on a single locked log, numeric
parse error or wildcard-sensitive output path. Its separate PS1 also had to be
extracted alongside CMD. The new generated CMD embeds its readable PS1 source,
uses a persistent Desktop output with writable fallbacks, isolates per-log and
summary errors, and uses literal-path .NET ZIP creation. It opens the result's
location after an interactive run. Oversized logs include their last 32 MiB,
explicitly recorded as tails. It never reads save files or changes game data.

Windows CI covers CMD-only execution, plain/space/Japanese/bracket paths,
exclusive optional-log locks, numeric-summary failure, invalid output fallback
and preserved fatal error exit codes. `build_feedback_launcher.py --check`
verifies the embedded collector matches the source.

The 19 portable suites, four ESP binary tests and generated audio checks cover
offline behavior. Windows DLL, audio/model asset and collector CI results must
pass before packaging. Delivered provenance binds the full runtime source,
audio/model inputs, private ESP builder and every packaged game file. Audible
VR timbre, perceived drag and mixer volume remain to be checked using
`DIAGNOSTIC_TEST_AUDIT5_JA.txt`.
