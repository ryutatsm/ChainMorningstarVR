# audit6 Blender軽量化・外観テスト

作業ブランチは `codex/blender-finish`。ゲームプレイ基準は引き続き audit6
`df3ef906a7927516263b567817900cc125d5f860`、引き継ぎツール基準は
`f10604b25d7ae0772356ad606b5fdfd3ae246cb3` です。mainへ統合せず、正式公開もしません。

## 結果

| 対象 | 変更前 | 変更後 |
| --- | ---: | ---: |
| 描画用三角形（血・衝突を除く） | 110,512 | 47,845 |
| 描画用NIF頂点（UV・法線の継ぎ目を含む） | 59,859 | 26,535 |
| 血用2形状を含むNIF三角形 | 213,072 | 87,289 |
| 描画メッシュ | 32 | 31 |

三角形は56.7%削減。`CMS_CMS_ROOT_cord` の8,960三角形を削除し、元の紐の配置・色・法線と
反射alphaを革へ投影しました。革の傷と押し込まれた形状は残っています。
木とエンブレムの細かな法線も元の高密度モデルから焼き込みました。
黒鉄のDDS・色、曲面のエンブレム画像、各NIFシェーダーの値はaudit6を引き継ぎます。

紐はノーマル表現なので輪郭の出っ張りを持ちません。その他の部品は双方向の高密度サンプルで
表面のずれ0.15 mm以内を検査しました。これは厳密なHausdorff距離の証明ではありません。
削減後の曲率・細部の見え方には実機確認が必要です。

## 保持した構造と確認内容

22ランタイムノード、19鎖節、75%の基準スケール、原点・親子関係・ローカル変換、15衝突形状を保持。
CMSのノード行と衝突行は元のバイト列を使用しています。連結成分、穴、面の向き、UVの範囲・向きも検査します。
既存の小変形用 `export_visual_edits.py` は変更していません。軽量化モデルを渡すと従来どおり拒否します。

`Tests/test_blender_optimization.py` は安全な書き出しと、単位・ノード変換・親・衝突・無断削除・
未適用モディファイア・大きな変形・UV反転・材質・未追跡メッシュ・旧エクスポーターの11拒否ケースを確認。
同じ保存ファイルからのCMS書き出しは同一になります。

固定niflyコミット `cca0a770094bb962fb28ea1fec5ea903e68fda8e` でWindows NIF writerをビルド。
元CMSからaudit6 NIFをバイト同一で再現することを先に確認します。
血用2形状は軽量化した鉄球から再生成し、ネイティブ血シェーダー、初期非表示、親、法線方向の
0.225 mmオフセット、全頂点・三角形の対応をwriterの再読込検査で確認しています。
DLL・ESP・掴み・摩擦・装備解除・音は上書きZIPに含めません。

変更DDSは `cms_leather_d`、`cms_leather_n`、`cms_wood_n`、`cms_emblem_n` の4枚だけ。
既存 `encode_dds.encode` でBC3/DXT5・11mipに変換し、全mipを再デコード。
normal GはNIFのV反転に合わせて1回だけ反転し、alphaは反射強度として保持します。

比較は同一カメラ・照明・AgX・96 samples・seed 1744。MCPから実際にシーン取得とレンダリングを実行しました。
引き継ぎPNGの `cms_metal_n.png` はIDAT末尾が欠けていたため、正常なaudit6 DDSからBlender向けに
デコードし直して変更前後の両方で使用しました。ゲーム用metal DDSは変更していません。

## 保存済み編集から再ビルド

`Assets/BlenderFinish/` に保存済み.blend、最終CMS、検査報告、元CMS、変更した4 PNGと各入力のSHA256があります。
作業ファイルは従来の `build/blender-work/Blender/ChainMorningstarVR_work.blend` にも残しています。
元の.blend、作業直前のバックアップ、元audit6 ZIPは上書きしていません。

```powershell
python Tools/Blender/validate_optimized_inputs.py Assets/BlenderFinish
blender --background --python Tools/Blender/export_optimized_visuals.py -- --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --out build/blender-finish/optimized.cms
python Tools/Blender/package_optimized_visuals.py --cms Assets/BlenderFinish/optimized.cms --baseline-cms Assets/BlenderFinish/audit6_baseline.cms --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --writer build/asset-exporter/Release/export_reference_nif.exe --out build/blender-finish-overlay/ChainMorningstarVR-audit6-visual-lowpoly-test.zip
```

通常のモデル／テクスチャ生成スクリプトを編集ファイルへ再実行しないでください。
`create_project.py` は既存の.blendへの上書きを拒否します。
専用 `blender-visual-test.yml` は保存済み編集を入力にし、元モデル生成やDDS全再生成を実行しません。
既存CIの生成先とは異なる `build/blender-finish-overlay/` に外観テストZIPを出力します。

Blenderのアドオンがファイル読込時にdirtyフラグを立てることがあるため、入力検査はdirtyだけでは判定しません。
保存ファイルを新しいバックグラウンドプロセスで開いたCLI出力、.blend/CMS/PNGのSHA256対応を検査します。

## 実機テストと戻し方

audit6本体を有効にしたままVortexへ外観テストZIPを導入し、競合は外観テストを後にします。
戻す場合は、この外観テストMODだけを無効化または削除し、Vortexで配置を更新してください。

Skyrim VR実機、FPS、接触、掴み、装備解除、血の実際の発生、音、xEditは今回未確認です。
ファイル検査の成功は実機動作や正式完成版の承認を意味しません。
