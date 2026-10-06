# Offhand investigation — 1.0.0-audit1, release blocked

The user reports that rc2 still cannot hold the ball. Do not equate a `held`
log entry, a successful build or portable tests with an in-game fix. No new
Vortex distribution or completed release is authorized by this evidence.
The work branch can be built for investigation. Main remains unchanged.

## Received evidence

Feedback `CMS-feedback-20261007-015630.zip`:
SHA-256 `a3745e905f2e7d2381299ab4ace1aca632a89b2c14ad2c951a18f5e60617fb6a`.
CMS log SHA-256 `06961d64b8ba0461f009817df9d45611d1a446aa366b69a780d299daa02db1a8`.
Only this bounded aggregate is committed; user logs are not published.

- Loaded version: 1.0.0-rc2. HIGGS 1101000, PLANCK 80100, visible VRIK scale ~0.85.
- Three native-head sessions; nine sampled selection-guard entries reject CMS picks.
- Two grip attempts rejected as `outside-head-reach`, at 0.44146255m and 0.600595m.
- One attempt at 0.1420509m captures input and enters hold at 01:54:45.847.
- Hold ends at 01:54:45.988: **141ms**, without a logged release reason.
- No warning/error lines. This does not imply functional success.

The rc2 selection exclusion did run, and no `higgs-two-handing` rejection is
recorded in this session. Retain it. The remaining release cannot be assigned
conclusively to input, a HIGGS busy transition, pose/chain limits or contacts
from the old log. The two distant attempts do not prove user mispositioning:
no simultaneous visible/solver/native pose comparison was recorded.

## Reproduced defects and changes

1. **Premature taut-chain release.** After gravity settling, the 12kg head is
   about 1.05660m from the anchor; authored reach is 1.04105769m. The old
   `reach + 0.04m` release condition leaves only ~2.45cm for ordinary outward
   hand motion. Continuous captured input and 0.20m/s outward movement release
   at 140ms at 50Hz (125–140ms across 45/50/72/90/120/144Hz).
   The continuous runtime test also fails against the actual rc2 header.
   This is a code defect consistent with the observed duration, **not proof
   that it caused this user's specific release**.

   Project the held target to the existing chain reach first. Retain contact
   while the palm is still inside the ball's grab envelope, with 4cm exit
   hysteresis relative to the acquisition envelope. Excessive separation,
   tracking jumps, obstruction, stale input and busy hands still release.
   No chain lengths, masses, collision shapes or physical filters are extended.

2. **Input withdrawal was treated as a new physical press.** The old capture
   state stored `accepted && pressed` as its edge history. If an earlier
   callback withdrew `accepted` while grip stayed pressed, its restoration
   could reacquire a still-held button. Store the received pressed bit
   separately; require a new edge of that bit before capture. Test withdrawal,
   restoration, release/repress, role changes and concurrent reset/polling.
   This latent issue was found in the follow-up audit; the rc2 log does not
   establish that it happened on the user's machine.

3. **The release evidence was insufficient.** Record the precise release branch,
   hold duration, input age/serial, received pressed/touched/accepted bits,
   palm distance/step, chain excess and target error. Include a previous
   post-write visual error and a native lag distance. Negative distances mean
   unavailable/not evaluated. Native lag is an asynchronous sample, not a
   same-frame alignment guarantee. Bits are received at SKSE priority 65;
   they are not independently observed hardware state.
   Bounded progress records at 0.5/2/5/10 seconds distinguish sustained holds
   from a start immediately followed by release. Lifecycle reset also records
   a reason. The collector keeps legacy missing reasons explicitly unknown.

## Validation scope

`Tests/offhand_runtime_ci.cpp` runs production RuntimeDriver, GripCaptureState,
OffhandGrabState and the fixed-step solver in one loop with a portable bridge:

- 45, 50, 72, 80, 90, 120, 144Hz crossed with scale 0.85, 1.0, 1.2: 21 cases.
- 7cm slow outward movement, inward lift and movement of both hands, three
  seconds continuous holding per case; target stays within authored reach.
- Gravity after release, repeated grab/release, teardown/reacquire and lost
  scene ownership. No retained grab across teardown.
- Head-floor feedback and player-body link contacts during continuous holding.
- Real input expiry releases; other release reasons are tested separately.
- World/local pose conversion and submitted native-pose contract checked.
  The fixture is **not** Skyrim, VRIK rendering or Havok callback execution.

All 14 portable CI programs pass locally, including the existing selection,
contact, damage/drop, sound and lifecycle tests. The three offhand/input tests
also run with AddressSanitizer and UndefinedBehaviorSanitizer; leak detection
is unavailable in this sandbox (`/proc`/ptrace restriction), so it is disabled
for those runs. Windows compilation and collector checks are separate CI gates.

Sources checked: HIGGS `93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee`
(`hand.cpp`, `hooks.cpp`, `pluginapi.cpp`), SKSEVR
`7ed497e87dc66935d6b6fbcc70a09ba2287307ad` (`InternalVR.cpp`, `Hooks_VR.cpp`),
PLANCK `f06fc953334aeea912975af6302e52e1bad92b01` (`ControllerStateCB`).
SKSE dispatch refreshes controller state and invokes callbacks on successful
polling; it does not cache this plugin's masked grip as original input.
The received SKSE log includes other callbacks before/after CMS; their mere
presence is not evidence of a conflict. No other mod settings were changed.

## Remaining release gate

1. Verify a continuous 10-second left-hand hold, slow lift, taut-chain movement,
   release and repeated regrab on the target installation. Record the actual
   release reason and visual result, not merely `held`.
2. If the ball still cannot be held, correlate received input with the release
   branch and observed hand/ball position before making another behavioral fix.
   Do not label this user's specific cause confirmed without that evidence.
3. Verify HIGGS ordinary grabs/two-handing with another weapon, menu/equip/load
   teardown, floor/wall interactions and the full existing release checklist.
4. Only then change investigation status and create a distributable ZIP.
   `Tools/package_visual_test.py` rejects the audit build label.

The old release-gate document remains required. This investigation neither
certifies the pending equipment-drop observations nor runs xEdit or the game.
