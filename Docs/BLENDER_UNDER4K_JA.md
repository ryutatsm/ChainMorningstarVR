# audit6：血用形状込み4,000三角形以下の外観テスト

ユーザー指定「4000以下」「エンブレムもノーマルマップ」のための明示的な再トポロジー経路です。
その後の革の上下端の厚み修正は [BLENDER_LEATHER_EDGES_JA.md](BLENDER_LEATHER_EDGES_JA.md) を参照。
現在の保存済み入力は革の縁を修正した3,996三角形版です。以下の数値は修正前の3,980三角形版です。
`codex/blender-finish` の保存済み編集を使用します。mainへ統合しません。
ゲームプレイ基準はaudit6 `df3ef906a7927516263b567817900cc125d5f860`、
ツール引き継ぎ基準は `f10604b25d7ae0772356ad606b5fdfd3ae246cb3` です。

## 数と形状

表示メッシュ31個の合計2,884三角形。血用2形状は各548三角形。
NIFの全33形状で **3,980三角形** です。非表示の血用形状を除外して目標を達成したものではありません。
衝突用Havok形状は描画三角形ではなく、audit6の15形状をバイト同一で保持しています。
前回表示47,845三角形から94.0%、audit6の110,512三角形から97.4%削減しました。

19鎖節は各80三角形。鉄球224、14棘合計224、曲面のエンブレム100三角形です。
柄の木120、革160。金具は元の表面を規則的にサンプリングして輪・穴を保ちます。
単純なDecimateは金具に穴、反転、UVの歪みを生じたため採用しません。

原本の位置・UVを再サンプリングし、法線を転写。元の紐の配置、傷、革の圧縮、木の傷、
エンブレムの浮き彫りを1024pxのテクスチャへ投影しました。
エンブレムは一定半径0.1216mの曲面土台です。図柄の高さ変位はメッシュに入りません。
鉄球内部に埋もれるエンブレムの裏側・側面と、棘の下4行の埋没した付け根も省きます。
棘の外側の肩と先端、14本の方向・UV・先端の小さな蓋は残します。

ノーマルの凹凸は輪郭を押し出しません。少ない三角形で近距離の輪郭が角張る場合があります。
前回0.15mmと同じ形状誤差ではありません。今回の外側表面検査は双方向サンプリング6mm以内、
UV・法線・穴・連結成分・面の向きの検査です。数学的な全表面距離保証ではありません。
鉄球の検査対象は外側コア、棘は外側肩以降で、省略した内部の面を検査対象から明示的に除きます。
全体の寸法を拡大しないことも検査します。画像比較は同じ視点・照明、AgX、96 samples、seed1744。

## 安全経路と検証

新規 `retopologize_under4k.py` と `export_under4k_visuals.py` を使用します。
従来の小変形 `export_visual_edits.py` と0.15mm `export_optimized_visuals.py` はこのモデルを拒否します。
低ポリ用エクスポーターも22ノード・19節・原点・単位・親子関係・変換・15衝突形状を厳密に維持。
三角形数は表示用とnative bloodの両方を合算して4,000を超えると拒否します。

`Tests/test_blender_under4k.py` は正しい保存済み編集、決定的な再書き出しと12件の不正入力拒否を検査。
単位、ランタイム変換・親、衝突、無断削除、未適用モディファイア、大変形、UV反転、
材質、予算変更、内蔵ノーマル画像欠落、従来の厳格経路の拒否を含みます。

固定nifly `cca0a770094bb962fb28ea1fec5ea903e68fda8e` のNIF writerを使用します。
先に元CMSからaudit6 NIFをバイト同一で再現してwriterを検証し、全33形状を再読込します。
血用2形状は新しい外側鉄球・棘・エンブレムと一対一で対応し、0.225mm法線オフセットと
ネイティブシェーダー・初期非表示・親を維持します。
変更DDSは革の色・法線、木の法線、エンブレムの法線4枚。BC3/DXT5、1024px、11mip。
normal G反転はゲームのV反転に対し1回だけ、alphaは反射強度として保持します。
BlenderのPrincipledのみの変更ではなく、ゲーム用NIFとDDSに反映しています。

## 再現と実機テスト

`Assets/BlenderFinish` の.blend、CMS、検査JSON、4 PNG、8入力のSHA256をCIの入力にします。
Windows専用CIは保存済み編集からZIPを作り、元モデル・テクスチャ生成スクリプトを呼びません。
元の.blend、audit6 ZIP、前回47k版は履歴・ローカルバックアップに残しています。

```powershell
python Tools/Blender/validate_optimized_inputs.py Assets/BlenderFinish
blender --background --python Tools/Blender/export_under4k_visuals.py -- --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --out build/under4k/optimized.cms
python Tools/Blender/package_optimized_visuals.py --cms Assets/BlenderFinish/optimized.cms --baseline-cms Assets/BlenderFinish/audit6_baseline.cms --blend Assets/BlenderFinish/ChainMorningstarVR_work.blend --textures Assets/BlenderFinish/textures --writer build/asset-exporter-ninja/export_reference_nif.exe --out build/blender-finish-overlay/ChainMorningstarVR-audit6-visual-under4k-test.zip
```

Vortexではaudit6本体を有効にしたまま、前回の47k外観テストを無効化して今回のZIPを導入。
競合は今回の外観テストを後にします。戻すには今回のテストのみを無効化して配置を更新。
前回へ戻したい場合は前回47kテストを再び有効にします。

DLL、ESP、音声はZIPに含めず、掴み・摩擦・装備解除・音の本体コードは変更しません。
VR実機、FPS、掴み・接触・血の実際の発生・装備解除・音、xEditは未確認です。
書き出し成功、画像比較、CI成功は実機動作や正式公開の承認ではありません。
