# 0.8.1: replace the hard-to-hear metal impact

The user reported 0.8.0 working but could not distinguish a heavy metal sound
when the ball hit the floor or objects. The supplied
`CMS-feedback-20261006-213939.zip` contains nine logged playback requests for
SNDR 0005CEF9, all with `playAccepted=true`, at intensity 0.906–1.0. These are
the first three logged impacts per relevant equip session, not a count of all
collisions. The log proves playback requests were accepted; it cannot prove
audibility, the user's mix level or how sound replacements alter the cue.

## Change

Replace `PHYGenericMetalHeavyImpact` with two different native sounds on the
same validated iron-head contact. Definitions were checked against the user's
private Skyrim.esm record export; no sound files are redistributed.

| Layer | IPCT | Selected sound in the supplied record | Handle volume |
| --- | --- | --- | --- |
| Large metal body | 0009150E, PHYBodyMetalLargeImpact | NAM1 0009150C; fallback SNAM 0009150D | 0.75 + 0.25 × intensity |
| Blunt strike on metal | 0004BB53, WPNBluntVsMetalImpact | SNAM 0003C826 | 0.48 + 0.18 × intensity |

The body cue is dominant and the strike layer gives it a recognizable metallic
attack. Resolved descriptors respect game sound replacements and category
settings. No vanilla form, shared attenuation, master volume or global pitch is
edited. Both cues start at the head's world position, without following its
subsequent movement. Only audio descriptors are played, not the IPCT's sparks,
decals or other effects.

An eight-handle impact pool holds four pairs. Every layer advances a slot even
when its descriptor is missing or its build fails, so pair lifetimes stay
aligned. The four-handle chain-rattle pool stays separate. Existing release
logic stops all handles on unequip, load, pause and teleport. Diagnostic lines
for the first three impacts per equip now report each layer's descriptor,
volume, build, position, volume-setting and playback acceptance separately.
Incomplete requests also emit a bounded warning.

The actual contact threshold (3 kg·m/s), 0.22-second cooldown, chain-only
non-damage policy, 75% geometry, 19 links, weight response and blood meshes are
unchanged. No collision logic change is justified by this audio feedback.

## Validation and target check

The existing impact-gating and runtime-contact-ordering tests cover the
unchanged contact trigger and lifecycle. Windows CI compiles the full bridge;
the package checks matched commit/source/output hashes for DLL and assets.
Build provenance in the delivered archive records the exact runs and hashes.
The new mix still needs listening in Skyrim VR.

1. Replace 0.8.0 with the complete 0.8.1 ZIP in Vortex and launch with SKSEVR.
2. Strike hard floor, a wall and a solid object with the ball, then try an NPC.
3. Check for an audible body impact plus metallic strike. Resting on a floor
   must not repeatedly clang; chain-only contacts must not trigger these cues.
4. If still inaudible, submit logs and say whether the normal chain rattle and
   other game weapon impacts are audible. The two layer result lines distinguish
   missing forms/build failures from accepted but inaudible playback.
