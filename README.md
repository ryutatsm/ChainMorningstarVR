# ChainMorningstarVR

**チェーンドモーニングスター — 1.0.0-audit5、実機診断版（正式版は保留）。**
Skyrim VR 1.4.15 / SKSEVR 2.0.12; requires HIGGS and PLANCK, with VRIK for
non-damaging player-body chain contacts. One-hand mace: damage44, weight17, value550.

The user reports successful equipment drops in audit4. Audit5 adds sustained
floor friction and original iron scrape, airborne swing and successful-disarm
audio. Contact/motion gains stop at rest; sound handles stop on teardown.
The feedback launcher now works as a single CMD and opens the created ZIP's
location. Real VR friction feel and audio balance still need confirmation.

- [日本語の導入・更新・操作](Docs/INSTALL_VR.md)
- [最終確認票](Docs/FINAL_CHECK_JA.txt)
- [Investigation, reproduced failures and remaining gates](Docs/SURFACE_AUDIO_AUDIT5.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Current geometry and project baseline](Docs/PROJECT_BASELINE.md)
- [Native physics design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Build using `Source/SKSE/PluginSkeleton` preset `vr-physics-test` (name retained for
compatibility). Pinned Windows workflows build the DLL and actual NIF/DDS assets
from one commit. `Tools/package_visual_test.py` verifies paired provenance and
creates candidate ZIPs only for an eligible candidate label. Audit builds are
blocked from candidate packaging. The separately authorized audit5 diagnostic
uses `Tools/package_runtime_diagnostic.py`, with complete source/hash validation
and separate runtime/packaging commits. Portable behavior tests run in CI.

Only one weapon is simulated at a time. Chain contacts bend/slide without pushing
the other body, self-collision or wrapping constraints. Body contacts use anatomical
capsules. Weapon meshes without usable CPU geometry are conservatively skipped.
Historical `ChainedMorningstarVR` packages and the removed native-proxy experiment
are not this project. The working branch does not merge or replace main.
