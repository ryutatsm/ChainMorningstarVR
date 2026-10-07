# ChainMorningstarVR — current audited baseline

This is the independent ChainMorningstarVR project. Do not mix runtime evidence
or assets from the older ChainedMorningstarVR project.
Audited main: `0777e257d64fcab908df03ff94e7a9af4ff1a0ee` (2026-10-06).
Current work: `astra/zero-base-audit-v050`, 1.0.0-audit6 (completed release blocked; user-requested diagnostic distribution). Main remains unchanged.

One-hand mace: damage44, weight17, value550; Japanese name
「チェーンドモーニングスター」; Eorlund sale; physical chain without chain damage;
actual head/spike contact; one unbiased 1/3 draw for the corresponding worn
enemy headgear/held weapon/shield instance on each eligible distinct contact episode.

## Current geometry and physics

- Approved design scaled to 75%, then five links added: 19 total.
- Handle42cm; first-to-last link-centre span87.230769cm; spacing4.846154cm.
- Core diameter24cm; spike envelope radius18cm; anchor-to-head reach104.105769cm.
- VRIK/body scale applies in addition to these authored dimensions.
- Fourteen spike directions plus core yield 15 convex collision hulls.
- Curved emblem, dark supplied material processing, native blood surfaces retained.
- 12kg head, 90Hz solver; swept non-damaging chain capsules; eleven VRIK body capsules.
- Two fixed endpoints while the empty physical left hand holds the right-hand ball.
- Chain contacts are one-way, without link-to-link collisions or closed-loop wrapping.

## Evidence and constraints

Current offhand input is the physical LEFT INDEX-FINGER TRIGGER (OpenVR button33).
The previous implementation hard-coded side grip/button2 and missed the user's
normal trigger grabs. Audit1 logged one 160ms side-grip hold; it did not observe
trigger attempts. Audit2 preserves side grip, reads/owns only the trigger near
the ball, and blocks delayed replay of that owned trigger. See
HEAD_STABILITY_AUDIT3.md. Audit2 feedback recorded a 29,962ms hold, but the user
reports unwanted motion, quarter-turns and floor bounce. Audit3 fixes continuous
orientation, full grip pose, split contact recovery and native endpoint continuity.
The audit3 user reports normal motion. Feedback 20261007-130041 records
13,184 ms and 20,119 ms trigger holds with normal releases, without warning/error
lines. This observation does not automatically pass all formal release gates.
Audit4 adds exact hand-body hits and shield worn-instance mapping. Gauntlets are
not targeted. Two-handed weapons share their right inventory slot across both
physical hands; continuous mesh/native contacts share one lottery opportunity.
See EQUIPMENT_DROP_AUDIT4.md for the scoped equipment-drop validation.
The taut-chain and selection fixes from prior versions remain.
Release gates now include the requested direct hand/shield behavior; pending observations remain pending.

The obsolete native-proxy-test mode remains removed. No PlayerCharacter
collision-node writes are permitted. The HIGGS-owned head compound, certified
contact router and synchronous exact-instance inventory removal remain in place.
Source/dependency revisions and complete output hashes accompany every package.

## Audit5 additions

The user reports audit4 equipment-drop behavior succeeded, without a feedback
archive. Audit5 applies supported static/kinetic friction (0.80/0.55) once per
90 Hz step. Three original PCM16 WAVs use new SNDR 802-804; WEAP/STAT remain
800/801. Source-generated audio and private-template ESP build are verified
by provenance. Single-file CMD collection creates a persistent ZIP despite
individual log errors and opens its location. See SURFACE_AUDIO_AUDIT5.md.

## Audit6 swing sound

The user reports audit5 works without issues but dislikes its sustained air loop.
Feedback 20261007-174749-135-34e27c confirms version audit5, zero CMS warnings/errors,
four real equipment drops and four accepted disarm cues, one 14,309 ms hold and
successful collection without a summary error. Audit6 changes only swing audio:
a 240 ms low one-shot, SNDR 803 non-looping, angular-motion-triggered repetition
with 280 ms minimum spacing. See SWING_AUDIO_AUDIT6.md. Audited support friction,
other sound samples, chain/head physics and equipment policy are retained.
