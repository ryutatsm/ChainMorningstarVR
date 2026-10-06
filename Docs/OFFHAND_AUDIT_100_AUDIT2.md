# Offhand input correction — 1.0.0-audit2

## Confirmed implementation defect

On 2026-10-07 JST the user clarified that grabbing uses the index-finger trigger;
side grip is bound to sheathing in their setup. HIGGS's official usage supports
trigger/grip, and its source reads `SteamVR_Trigger` (button33) as well as grip
(button2). CMS through audit1 read **only button2**. It never observed or captured
the user's trigger attempt. The earlier instruction to use side grip was wrong
for the requested interaction. This is an input-mapping defect, not evidence that
the user held the wrong button or released their normal grab button too early.

Feedback `CMS-feedback-20261007-025659.zip` has SHA-256
`c7618785c82ff6ae6b019ac1068d3000787bc05dd98ce0fbf1db2a6126f1d397`.
Only bounded observations are committed; raw user logs remain private.

- audit1 loaded correctly, HIGGS1101000 / PLANCK80100, visible VRIK scale~0.85.
- One recorded side-grip hold: 02:55:37.167 to 02:55:37.327 (160ms).
- Release branch `grip-released`: received pressed=false, touched=true,
  accepted=true, inputAgeMs=1. No chain-limit, obstruction or stale-input release.
- Previous post-write visual error was about0.32mm in that record.
- There was no trigger-state recording. This log does not establish the timing
  of the user's trigger press or release, nor prove a 10-second physical hold.

The matching GripKickVR0.11.0 source package identifies itself as SKSE version12,
matching this session's registration. Its early/late callbacks restrict filtering
to axis-button stick clicks and explicitly exclude button2 and button33. PLANCK's
callback reads joystick axes. HIGGS executes after CMS (66 vs65). These source
checks do not show those callbacks deleting the grip here, and their presence
alone must not be described as a proven conflict.

## Correction

- Physical **left index-finger trigger**, OpenVR button33, is the CMS ball grab.
- Side grip/button2 remains untouched, including while CMS holds the ball.
- Only a fresh trigger press while the empty left hand is near the right-hand
  CMS ball can capture input. No remote pulls, held-button stealing, or right-hand
  trigger capture. Existing HIGGS busy-hand, scale/pose, selection and chain gates
  remain in force.
- A captured trigger is masked before HIGGS. A final callback masks only that
  same owned trigger (including the release sample) if HIGGS replays delayed
  input. It never clears other buttons, grip, axes or the acceptance flag.
- Logs identify `button=left-trigger`, received trigger bits, sideGripPressed,
  the received pressed bitmask, and `trigger-released`. Historical log prefixes
  containing the word `grip` mean a hold event, not the current input button.
- The collector records `offhand_grab_button=left-trigger` for this version.

## Verification

The actual controller-state ABI and button decoder now live in portable
`OffhandInputCore.hpp`, shared by the Windows callbacks and tests. Previous
runtime tests injected an abstract bool and therefore missed the mapping defect.

- Button2 alone does not acquire; button33 does. All unrelated pressed/touched
  bits, packet number and ten axis values remain unchanged, including right-hand
  combat input and unarmed ordinary HIGGS grabs.
- Delayed trigger replay is removed only for the captured press and its release
  sample; reset, stale input, different packets, declined input and role changes
  cannot create a new hold.
- Changing the decoder back to button2 makes the new input regression fail.
- Production RuntimeDriver/solver/input/hold integration: 10-second trigger
  holds at45/50/72/80/90/120/144Hz and scales0.85/1/1.2. Side grip falls at160ms
  without releasing CMS. Includes slow lifting, taut movement, gravity after
  release, repeated grabs, teardown, scene ownership loss, floor/body contacts
  and actual input timeout.
- All portable C++ behavior programs and the vendor contract lint pass locally.
  The tests are not a Skyrim/Havok/VR runtime and do not verify visual hand
  animation or engine button routing.
- Windows compilation and collector execution must pass before packaging;
  exact source/output hashes and CI run IDs are included in the diagnostic ZIP.

## Remaining actual-machine checks

Use `DIAGNOSTIC_TEST_AUDIT2_JA.txt`: trigger hold/lift/release/regrab, side-grip
sheathing, menus/equip/load, other HIGGS grabs and normal attacks. A start line
alone is insufficient. The user's prior authorization permits a diagnostic
package; **completed release remains unverified**. Existing combat, equipment
drop, long-session and xEdit release gates remain pending. Main is unchanged.

## Primary references

- [HIGGS official usage](https://www.nexusmods.com/skyrimspecialedition/mods/43930), Grabbing/Pulling and Configuration.
- [HIGGS hand.cpp](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/src/hand.cpp), ControllerStateUpdate/ShouldRestrictTrigger.
- [HIGGS default config](https://github.com/adamhynek/higgs/blob/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee/include/config.h), EnableTrigger and EnableGrip both default true.
- [SKSEVR input dispatch](https://github.com/Odie/sksevr-mirror/blob/7ed497e87dc66935d6b6fbcc70a09ba2287307ad/skse64/InternalVR.cpp), ascending callback order and per-poll state.
