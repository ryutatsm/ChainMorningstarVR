# ChainMorningstarVR

**チェーンドモーニングスター — 1.0.0-rc2, Vortex-installable release candidate.**
Skyrim VR 1.4.15 / SKSEVR 2.0.12; requires HIGGS and PLANCK, with VRIK for
non-damaging player-body chain contacts. One-hand mace: damage44, weight17, value550.

The approved dark reference model is scaled to 75% with 19 physical links,
a heavy 12kg head, spatial metal impacts, curved emblem and native blood surfaces.
The inventory preview is upright and the weapon name is Japanese. The free left
hand can request a ball hold while the right hand equips the weapon. Certified
head/equipped-weapon impacts feed one unbiased 1/3 exact-instance equipment-drop draw.

The supplied rc1 feedback confirms two in-range/nearby grip attempts were rejected
as `higgs-two-handing`: HIGGS selected the CMS ball as the other hand's weapon
before CMS could arm. Rc2 excludes the active right-hand CMS filter signature
only from HIGGS CustomPick2 selection queries during HIGGS Update. Actual physical
collision comparisons and settings are untouched. Busy-hand checks remain.
The regression fixture reproduces rc1's ownership ordering and verifies capture,
release and unchanged physical-filter decisions. The target-machine retest is pending.

- [日本語の導入・更新・操作](Docs/INSTALL_VR.md)
- [最終確認票](Docs/FINAL_CHECK_JA.txt)
- [Candidate changes, evidence and remaining gates](Docs/RELEASE_STATUS_100_RC2.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Current geometry and project baseline](Docs/PROJECT_BASELINE.md)
- [Native physics design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Build using `Source/SKSE/PluginSkeleton` preset `vr-physics-test` (name retained for
compatibility). Pinned Windows workflows build the DLL and actual NIF/DDS assets
from one commit. `Tools/package_visual_test.py` verifies paired provenance and
creates the candidate ZIP and feedback tools. Portable behavior tests run in CI.

Only one weapon is simulated at a time. Chain contacts bend/slide without pushing
the other body, self-collision or wrapping constraints. Body contacts use anatomical
capsules. Weapon meshes without usable CPU geometry are conservatively skipped.
Historical `ChainedMorningstarVR` packages and the removed native-proxy experiment
are not this project. The working branch does not merge or replace main.
