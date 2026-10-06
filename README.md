# ChainMorningstarVR

**チェーンドモーニングスター — 1.0.0-audit1、実機診断版（正式版は保留）。**
Skyrim VR 1.4.15 / SKSEVR 2.0.12; requires HIGGS and PLANCK, with VRIK for
non-damaging player-body chain contacts. One-hand mace: damage44, weight17, value550.

Rc2 feedback shows a captured hold lasting only 141ms. A continuous runtime
fixture reproduces a premature taut-chain release after ~140ms; audit1 fixes
that limit and a separate input-withdrawal edge bug. It adds release reasons,
input/pose evidence and bounded sustained-hold records. The user's exact
release branch was not logged by rc2, so **the target-machine cause and fix
remain unconfirmed**. See the [audit and remaining checks](Docs/OFFHAND_AUDIT_100_AUDIT1.md).

The 75% dark model, 19 links, heavy head, metal sounds, curved emblem, native
blood surfaces, Japanese name, upright preview and existing combat integration
are retained. At the user's explicit request, the matched audit1 build is
provided as a Vortex-installable diagnostic package for target-machine testing.
[日本語テスト手順](Docs/DIAGNOSTIC_TEST_AUDIT1_JA.txt). Completed release remains blocked.

- [日本語の導入・更新・操作](Docs/INSTALL_VR.md)
- [最終確認票](Docs/FINAL_CHECK_JA.txt)
- [Investigation, reproduced failures and remaining gates](Docs/OFFHAND_AUDIT_100_AUDIT1.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Current geometry and project baseline](Docs/PROJECT_BASELINE.md)
- [Native physics design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Build using `Source/SKSE/PluginSkeleton` preset `vr-physics-test` (name retained for
compatibility). Pinned Windows workflows build the DLL and actual NIF/DDS assets
from one commit. `Tools/package_visual_test.py` verifies paired provenance and
creates candidate ZIPs only for an eligible candidate label. Audit builds are
blocked from candidate packaging. The separately authorized audit1 diagnostic
uses `Tools/package_runtime_diagnostic.py`, with complete source/hash validation
and separate runtime/packaging commits. Portable behavior tests run in CI.

Only one weapon is simulated at a time. Chain contacts bend/slide without pushing
the other body, self-collision or wrapping constraints. Body contacts use anatomical
capsules. Weapon meshes without usable CPU geometry are conservatively skipped.
Historical `ChainedMorningstarVR` packages and the removed native-proxy experiment
are not this project. The working branch does not merge or replace main.
