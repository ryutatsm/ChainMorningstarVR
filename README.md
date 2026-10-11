# ChainMorningstarVR

## 現在の仕上げ状況（2026-10-11）

作業ブランチは`codex/blender-finish`。最新は①の重い衝撃音を含む統合版。
合計3,996三角形（表示2,900・血用1,096）、鎖19節、22ノード、21DDSを維持する。
ゲーム用ソースは`57e61bee55fcb6fad566687e13db804393662bfe`、DLL内部ラベルは`1.0.0-audit8`。
ユーザーから完成版への仕上げ依頼を受けた後、起動・ロード時のクラッシュ増加が報告された。
完成版の確定前に[クラッシュの比較テスト](Docs/CRASH_TRIAGE_20261011_JA.md)を行う。
配置済み28ゲーム用ファイルは①統合ZIPと全SHA256一致。外観・音の合意を全安定性項目の合格へ読み替えない。
旧モデル生成でBlender編集を上書きしない。main統合・正式公開は行っていない。

以下はaudit6時点の開発・検証記録。最新の版と残る確認は上記リンクを参照。

**チェーンドモーニングスター — 1.0.0-audit6、実機診断版（正式版は保留）。**
Skyrim VR 1.4.15 / SKSEVR 2.0.12; requires HIGGS and PLANCK, with VRIK for
non-damaging player-body chain contacts. One-hand mace: damage44, weight17, value550.

The user reports audit5 works without issues; its feedback ZIP confirms collection,
zero CMS warning/error entries and four successful equipment drops with accepted
disarm sound requests. Audit6 replaces the sustained air noise with a short low
swing one-shot. Continuous circular motion retriggers one pulse per revolution;
backstrokes retrigger separately and contact/holding cancels the sound.
The revised timbre still needs the user's listening check in VR.

- [日本語の導入・更新・操作](Docs/INSTALL_VR.md)
- [最終確認票](Docs/FINAL_CHECK_JA.txt)
- [Investigation, reproduced failures and remaining gates](Docs/SWING_AUDIO_AUDIT6.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Current geometry and project baseline](Docs/PROJECT_BASELINE.md)
- [Native physics design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Build using `Source/SKSE/PluginSkeleton` preset `vr-physics-test` (name retained for
compatibility). Pinned Windows workflows build the DLL and actual NIF/DDS assets
from one commit. `Tools/package_visual_test.py` verifies paired provenance and
creates candidate ZIPs only for an eligible candidate label. Audit builds are
blocked from candidate packaging. The separately authorized audit6 diagnostic
uses `Tools/package_runtime_diagnostic.py`, with complete source/hash validation
and separate runtime/packaging commits. Portable behavior tests run in CI.

Only one weapon is simulated at a time. Chain contacts bend/slide without pushing
the other body, self-collision or wrapping constraints. Body contacts use anatomical
capsules. Weapon meshes without usable CPU geometry are conservatively skipped.
Historical `ChainedMorningstarVR` packages and the removed native-proxy experiment
are not this project. The working branch does not merge or replace main.
