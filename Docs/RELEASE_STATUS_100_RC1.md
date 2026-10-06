# 1.0.0-rc1 release status

This archive is a release candidate, not a completed-release claim.
The existing `Docs/RELEASE_GATE_NEW_BUILD.md` remains authoritative and unchanged.
Main is not merged. The working branch is `astra/zero-base-audit-v050`.

## Confirmed evidence

The user reports 0.9.0 working normally. The supplied 2026-10-07 00:20:52 JST
feedback contains the 0.9.0-physics-test DLL log, not a log from this candidate.
It records three native 15-hull head attachments, eleven VRIK body capsules,
actual player-body chain contacts, and successful playback requests for both
metal impact layers. No CMS warning/error/critical line appears.
There are twelve sampled certified head contacts: six not-enemy and six
no-eligible-worn-instance. They do not establish a successful eligible draw.
No actual offhand-held or equipment-drop-reference entry occurs.
Only log hashes and aggregate evidence are committed; raw user logs are not published.

## Candidate changes

- Serialize controller capture, role changes and reset with one scalar-state mutex.
  The old independent atomic load/store could restore a claim after teardown.
- Keep a held grip consumed until release, but clear it on teardown and physical
  device-role changes. Require a fresh release/press after reset.
- Log bounded offhand attempts with distance, capture state and rejection reason.
- Collect the actual runtime version and sampled outcome counts in runtime_summary.json.
- Consolidate installation/update/rollback instructions, provenance and final checks.
- Preserve 0.9.0 ESP, geometry, textures, sound mix, body contacts and drop probability.

## Unresolved compatibility and target gates

HIGGS 93bf67b `Hand::IsInGrabbableState` excludes SelectedTwoHand. HIGGS can
select an equipped one-hand mace for two-handing as the offhand approaches it.
Its public interface does not distinguish that state from pending grab/pull states.
CMS therefore retains the conservative CanGrabObject guard instead of treating
all unheld hands as free. A ball-grab attempt may be rejected with
`reason=higgs-not-grabbable`. This is a source-audit risk, not a demonstrated
cause of the absence of held entries in the user's log; no attempt was logged
by 0.9.0. It remains a blocker to claiming universal offhand compatibility.
Primary pinned source: https://github.com/adamhynek/higgs/tree/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee

Remaining gate evidence includes actual offhand hold/release and blocked-hand
behavior; helmet and exact equipped-weapon drops, preserved enchantment/tempering,
negative and fatal-hit cases; native combat accounting, fast/tip-only contacts
and gaps; blood and sound observations; lifecycle/cell changes and ten minutes
of combat; both-hand appearance and merchant purchase/buy-back/stock reset on
new/existing saves; xEdit Check for Errors against the installed masters.
The portable tests and Windows CI verify code/build contracts, not these observations.
Use FINAL_CHECK_JA.txt to record target results. Absence of a sampled log entry
must not be converted into a pass or a definitive failure.
