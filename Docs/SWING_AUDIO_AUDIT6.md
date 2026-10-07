# Audit6 — short low swing sound

The user reports audit5 works without issues but dislikes the air sound and
requests a short low "boon", repeated "boon, boon, boon" during rotation.
The attached `CMS-feedback-20261007-174749-135-34e27c.zip` has SHA256
`a6e56c112d55d253ce3797d909c988224937f6a4405c1894ee6a9156b281959c`.
Its audit5 log/summary contain zero CMS warning/error entries, four actual drop
references and four accepted disarm cues, one 14,309 ms hold and a successful
collector run without summary errors. Request acceptance is not an acoustic
measurement; the user's report supplies the separate in-game observation.

## Change

The old 2-second air loop was broad continuous turbulence. It continued at
steady gain when the user kept rotating the head, so changing gain alone could
not create clearly separated low swings.

The replacement is an original 240 ms mono PCM16/44.1 kHz transient with low-mid
turbulence, a soft attack and descending low resonance. More than 90% of its
spectral energy is below 700 Hz. The scrape and disarm WAV generation retains
its exact audit5 random stream. Only air_cut.wav changes.

SNDR 803 keeps its FormID, file path and native spatial/category metadata but
is now explicitly non-looping. The game-thread audio service plays the complete
sample once on each gate event and lets its quiet tail finish. Ordinary silent
frames do not stop/restart it. Contact, holding and existing teardown cancel it.

The gate qualifies movement over 35 ms, then integrates angular speed from
`cross(head-anchor, headVelocity-anchorVelocity) / radiusSquared`. At ordinary
rates, one revolution requests one sample; reversing the angular axis qualifies
a new backstroke. Translation of the whole player is removed, radial movement
does not continually retrigger, and the minimum 280 ms inter-shot interval
leaves a gap after the 240 ms sample. Very rapid rotation is rate-limited rather
than layering noise. Short threshold jitter cannot repeatedly restart the sound.

The physics solver, support friction, chain contacts, damage/equipment policy,
grabbing and other audio samples are unchanged. The audit5 collector remains
compatible because sampled air-start logging keeps its original prefix; the
new `mode=swing-one-shot` suffix identifies the changed path.

## Verification

The portable motion suite exercises five frame rates (45/72/90/120/144 Hz),
three rotation planes and four normal rotation speeds for 12 seconds each.
It verifies pulse counts/phase, backstrokes, high-speed rate limiting, radial
motion, held/contact suppression, scrape gain, single-frame noise, reset and
invalid input. Existing core suites must remain green. Independent ESP binary
tests assert 802 loops and 803/804 do not. Audio checks cover format, duration,
spectral balance, soft ends, peak/RMS/DC and exact file hashes.

Windows DLL and asset workflows must succeed on the same source commit before
packaging, and the packager verifies the non-looping descriptor, new runtime
marker and all source/output manifests. Subjective timbre, spatial mix volume
and actual VR swing cadence remain to be heard by the user.
