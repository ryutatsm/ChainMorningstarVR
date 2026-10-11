# audit6：革の上下端の厚み

ユーザー指定「上下のポリゴンのフチが見えるので、少し追加して木につける」に対応した編集です。
直前の3,980三角形版を基準に、革のみを変更しました。

上下端は元の16分割の輪郭を保ち、各24三角形の環状面を追加。
内側8頂点は理想円ではなく、実際の木の三角形を切った断面に合わせています。
隙間を防ぐため、木に0.08mm埋めます。見える厚みは元の革と木の距離により約2.45〜6.33mm。
縁のUVには既存の革テクスチャの端の帯を使い、新しい画像は追加しません。

4,000以下を保つため、革の中央の軸方向分割を1行減らし、32三角形整理しました。
保持する頂点の位置・UV・転写法線、上下端の外形はそのままです。
省いた行の頂点と隣の2行の線形補間との差は最大約0.731mmです。
Blenderのカスタム法線再格納には0.005度未満の丸めが生じます。
外側表面の距離は従来の双方向サンプリング6mm検査を通します。
追加した環状面は元の革の側面とは異なるので、木との接触・形状・UV・法線を専用契約で検査します。

革160 → 176、表示用2,884 → 2,900、血用1,096を加えて **3,996三角形**。
木、金具、鉄球、棘、曲面エンブレム、19鎖節は直前の版と同じ頂点・UV・法線・面です。
22ノード、15衝突形状、原点、階層、75%寸法、4PNG/DDS、21内蔵画像を維持します。
紐とエンブレムは引き続きノーマルマップで表現します。

## 再現と検査

`Tools/Blender/contracts/leather_edge_source.cms` は直前版をSHA256で固定した参照です。
`finish_leather_edges.py` が決定的な形状を作り、`leather_edge_contract.py` が検査します。
`export_under4k_visuals.py` とWindowsのパッケージ工程の両方で検査し、
接触面の変形、UV変更、接触ポリシー変更、他のメッシュの微小変更も拒否します。
既存12検査に5検査を加え、保存済みファイルからのCMSは決定的です。
従来の厳格エクスポーターを緩めず、今回指定された革の縁のみを許可します。

```powershell
blender --background --python Tools/Blender/finish_leather_edges.py -- --blend build/blender-work/Blender/ChainMorningstarVR_before_leather_edge.blend --out build/blender-work/Blender/ChainMorningstarVR_leather_edge_work.blend
blender --background --python Tools/Blender/export_under4k_visuals.py -- --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --out build/leather-edge/optimized.cms
python Tools/Blender/validate_optimized_inputs.py Assets/BlenderFinish
python Tools/Blender/package_optimized_visuals.py --cms Assets/BlenderFinish/optimized.cms --baseline-cms Assets/BlenderFinish/audit6_baseline.cms --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --writer build/asset-exporter-ninja/export_reference_nif.exe --out build/blender-finish-overlay/ChainMorningstarVR-audit6-leather-edge-test.zip
```

比較画像は同じ視点・照明・AgX・96 samples・seed1744で上下端を確認。
画像の結果とゲームでの見え方は同一とは限りません。
ゲーム用NIFを再読込し、元audit6 NIFのバイト同一再現、血用形状、DDSも検査します。
生成スクリプトで保存済みBlender編集を上書きせず、Windows CIは固定の入力だけを使用します。

## Vortexと戻し方

audit6本体を有効にしたまま、以前の外観テスト（47k版・3,980三角形版）を無効化。
今回の革の縁テストZIPを導入し、競合では今回のテストを後にします。
戻すには今回のテストだけを無効化して配置を更新。必要なら前回のテストを再び有効にします。
ZIPはNIFと4DDSのみをゲームへ上書きし、DLL・ESP・音声を含めません。
実機・FPS・xEdit・実際の掴み/摩擦/血/装備解除/音は未確認。main統合・正式公開はしません。
