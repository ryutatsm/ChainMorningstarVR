# ChainMorningstarVR — current audited baseline

This is the independent ChainMorningstarVR project. Do not mix runtime evidence
or assets from the older ChainedMorningstarVR project.
Audited main: `0777e257d64fcab908df03ff94e7a9af4ff1a0ee` (2026-10-06).
Current work: `astra/zero-base-audit-v050`, 1.0.0-audit3 (completed release blocked; user-requested diagnostic distribution). Main remains unchanged.

One-hand mace: damage44, weight17, value550; Japanese name
「チェーンドモーニングスター」; Eorlund sale; physical chain without chain damage;
actual head/spike contact; one unbiased 1/3 draw for the corresponding worn
enemy headgear/weapon instance on each eligible distinct contact episode.

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
Physical stability remains unverified.
The taut-chain and selection fixes from prior versions remain.
RELEASE_GATE_NEW_BUILD.md is unchanged; pending observations remain pending.

The obsolete native-proxy-test mode remains removed. No PlayerCharacter
collision-node writes are permitted. The HIGGS-owned head compound, certified
contact router and synchronous exact-instance inventory removal remain in place.
Source/dependency revisions and complete output hashes accompany every package.
