# Blender仕上げ用引き継ぎ — audit6

2026-10-11。目的は、動作確認済みモデルの外観をWindowsのCodexとBlender 4.5で微調整できるようにすること。
今回の引き継ぎではゲーム内の外観、物理、音、装備解除処理を変更していない。
作業ブランチは `codex/blender-handoff-audit6`。基準コミットは
`df3ef906a7927516263b567817900cc125d5f860`。mainは完成状態の基準ではない。

## 最初に読む情報

- ユーザーはaudit6を実機確認し「とても良い」と報告済み。
- audit6の新しいfeedback ZIPは未受領。手元の詳細ログはaudit5以前なので混同しない。
- xEdit Check for Errors、全ライフサイクル試験等の正式リリース項目は全件確認済みではない。
- `Docs/PROJECT_BASELINE.md` と `Docs/RELEASE_GATE_NEW_BUILD.md` を読む。
  ゲーム内の成功報告は尊重し、未確認項目を合格に書き換えない。
- 古い生成済みファイルはaudit6と異なることがある。今回の.blendはaudit6のActions成果物
  `11471381940`（asset build run `37598017954`）から作成し、配布MOD内のNIF/DDSと照合する。
- 新たな修正部位・程度はまだ指定されていない。接続と比較画像の準備後、ユーザーの具体的な指示で調整する。

## 引き継ぎZIP

ZIPは編集用。Vortexへ入れるものではない。中の `Baseline/ChainMorningstarVR-1.0.0-audit6-diagnostic.zip`
だけが動作確認済みのMOD本体で、復帰用に含まれる。既に同版を導入済みなら再導入しなくてよい。

- `Blender/ChainMorningstarVR_audit6.blend`：Blender 4.5.3 LTSで作成。21画像を内蔵。
- `Blender/textures/`：配布DDSをデコードした編集用PNG。元の生成用原画とは区別する。
- `Baseline/reference_mesh.cms`：読み取り基準。59,859頂点、110,512三角形、32メッシュ。
- `Baseline/asset_manifest.json` / `ASSET_BUILD_PROVENANCE.json`：元ビルドの記録。
- `Preview/`：Blenderで実レンダリングした比較用画像。ゲーム照明の再現ではない。
- `CODEX_START_PROMPT_JA.txt`：ローカルCodexの最初のチャットへ貼り付ける文章。
- `HANDOFF_MANIFEST.json` / `SHA256SUMS.txt`：引き継ぎ内容の識別・検証用。

ソースはGitHubの上記ブランチから取得する。ZIPに古いソース一式は同梱しない。
GitHubへ接続できない場合も.blendは単独で開けるが、MODへの書き戻しにはソースが必要。

## Windowsで始める

1. ZIPを `C:\ModWork\ChainMorningstarVR_Blender_Handoff` 等に展開する。
2. Blender 4.5で現在の別プロジェクトを保存し、同梱.blendを開く。
3. 3Dビューで `N` → MCP for Blender。既存アドオンのサーバーを開始し、ポート9876の接続表示を確認する。
   ユーザーの以前の構成はMCP for Blender v1.8、Connected on port 9876。
   これは過去の確認結果であり、現在のPCへこちらから接続したことを意味しない。
4. WindowsのCodexで「ローカル」の作業として展開先フォルダーを開く。
5. `CODEX_START_PROMPT_JA.txt` 全文を貼り付ける。Codexがソース取得、作業コピー、シーン情報・画像確認を行う。
6. 準備できたら「革の中央の凹凸を少し深く」など、対象と程度を伝える。必要なら新しい参考画像を添付する。

既存の `%USERPROFILE%\.codex\config.toml` には次の接続が設定されていた。
動いていれば変更不要。設定ファイル全体を置き換えない。

```toml
[mcp_servers.blender]
command = "uvx"
args = ["mcp-for-blender"]
env = { BLENDER_HOST = "localhost", BLENDER_PORT = "9876" }
```

接続しない場合はBlenderを開いたままMCPサーバーとポートを確認する。
設定を直した場合はCodexを完全終了して起動し直す。複数のAIクライアントから同時に操作しない。
Blenderアドオンの再インストールやバージョンアップを最初の手段にしない。

## 維持する仕様

- 片手メイス、日本語名「チェーンドモーニングスター」。damage44 / weight17 / value550。
- 全体75%化済み、追加5節で鎖19節。二重に75%化しない。
- 柄42cm、鉄球コア直径24cm、トゲ14本、球コアとトゲの計15凸形状。
- 12kgの鉄球、90Hzの物理、鎖の無ダメージ接触、身体接触。
- 右装備時、空いた左手の人差し指トリガーで鉄球を掴む。側面グリップへ戻さない。
- 敵の頭装備／当たった手の武器・盾を、有効な接触ごとに1/3で落とす。小手を落とす意味ではない。
- 床摩擦、擦過音、打撃音、現在の短い低い「ブン」の周期音。
- 血はNIF生成時に鉄球・トゲ・エンブレムの形状から作り直す。
- 黒鉄、使い古した革、太い手元、木の凹凸、曲面に沿った供給画像のエンブレム。

## Blenderシーンの構造

| コレクション | 用途 |
| --- | --- |
| `01_Runtime_nodes_KEEP` | 22個の実行時ノード。原点・階層・姿勢を維持。初期状態では非表示 |
| `02_Visuals_EDIT` | 32個の編集対象。木、革、鉄、トゲ等をマテリアル別に分離 |
| `03_Collision_reference_KEEP` | 15個の当たり判定参照。非表示、レンダー対象外。必要時だけ表示 |
| `04_Preview_lights_cameras_ONLY` | 全体、鉄球、柄の比較用カメラと照明。MODには書き出さない |

1単位=1m、Z-up。柄の長軸はroot +Y、鎖アンカーのlocal +Zがroot +Yを向く。
glTF経由の軸変換をせずCMSから直接作成した。BlenderのRigid Bodyは設定しない。
ゲームの物理はDLLで動き、Blender内で振り回しても同じ挙動を再現するわけではない。
`rough_wood`、`compressed_leather`、`hammered_iron_core`、`battered_spike_00`等の頂点グループを使用できる。
`CMS_ROOT`、`CMS_ChainAnchor`、`CMS_LinkNode_00`～`18`、`CMS_HeadNode`を改名・移動しない。

## 形状をMODへ戻す

最初は編集モードでの小さな頂点変形と既存UVの調整を行う。
エクスポーターは未編集部分、ノード、当たり判定を元のCMSのまま維持する。
頂点数・三角形・マテリアル構成を変える編集、未適用モディファイア、2mmを超える変形、外周bounds拡大は停止する。
2mmは作業範囲の制限であり、接触精度を保証する許容誤差ではない。調整箇所は実機で確認する。
リメッシュや大きな変形を求められた場合は、衝突形状・DLL接触面・ESP boundsも一緒に更新する設計へ進む。
停止条件を消して通すことはしない。

作業コピーを保存し、Object Modeにする。以下はリポジトリ直下のPowerShell例。
`$BlenderExe` はインストール先に合わせる。

```powershell
$BlenderExe = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
& $BlenderExe --background 'build/blender-work/Blender/ChainMorningstarVR_work.blend' --python 'Tools/Blender/export_visual_edits.py' -- --out 'build/blender-edited/reference_mesh.cms'
```

初回は未編集で `Tests/test_blender_handoff.py` を同じBlenderから実行して経路を確認する。
スクリプトは標準のBlender付属numpyを使う。pipで別のbpyをWindowsへ入れる必要はない。
未編集CMS SHA256は `0319d497343fc72afa85f68ac5c3444df4042ac920633aea96eebe19e1d3ca57`。

NIF writerは既存 `Source/NIF/ASSET_BUILD.md` の固定niflyリビジョンからビルドする。
使えるコンパイラがない場合は、ソースと入力を固定したWindows CIジョブを追加して作る。
既存のwindows-nif-build.ymlをそのまま走らせると、ジェネレーターの元モデルが作られ、Blender編集は反映されない。

```powershell
python Tools/Blender/package_visual_edit.py --cms build/blender-edited/reference_mesh.cms --baseline-cms build/blender-work/Baseline/reference_mesh.cms --baseline-zip build/blender-work/Baseline/ChainMorningstarVR-1.0.0-audit6-diagnostic.zip --writer build/asset-exporter/Release/export_reference_nif.exe --out build/blender-edited/ChainMorningstarVR-visual-test.zip
```

このコマンドは接触面一致の確認、NIF生成・再読込、由来記録、Vortex用の**外観テスト上書きZIP**を作る。
audit6本体を有効にしたまま導入し、競合はテストMODが後になるようにする。
戻す場合はテストMODだけ無効化する。DLL・ESP・音声は既存audit6を使用し、正式版とは扱わない。
変更なしの往復試験に成功しても、実際に変形した部位の見た目・接触・血は実機確認が必要。

## テクスチャを調整するとき

- 21枚のPNGはaudit6のBC3 DDSからデコードしたもの。元のDDSも同梱MODにある。
- `_d`は色、`_n`は法線RGBと反射強度alpha、`_m`は環境反射マスク。
- 編集用PNGのnormal GはCMS/Blender用に反転を戻してある。
  NIF向けDDSにする際は既存 `Source/Textures/encode_dds.py` がGを1回反転する。二重反転しない。
- normal alphaを透明度として消さない。エンブレムの画像内容と曲面UVを維持する。
- BlenderのPrincipled roughnessを変えただけではSkyrimの質感は変わらない。
  色・凹凸は画像に保存し、必要に応じてNIF側シェーダー値も理由を明記して変更する。
- 変更していないDDSはaudit6のものをそのまま使用する。全DDSを無意味に再圧縮しない。
- 本エクスポーター／上書きZIP作成ツールは形状用。テクスチャ変更時は選択した画像のみを
  既存encode関数でBC3・11mipへ変換・検証し、変更DDSを上書きZIPへ追加して記録する。

## 再現可能な最終成果物へ

採用した編集を.blendとCMS/PNGとして保存し、それぞれのhashと変更理由を記録する。
正式ビルドを行う前に、新しい編集入力を読むCIルートを用意し、provenance対象へ含める。
元の `generate_reference_mesh.py` を編集結果の上に実行しない。
元のasset_manifestを変更後の形状の証明として使い回さない。新しいbounds・頂点・材質記録を作る。
新規の作業ブランチで保存し、元の動作確認済み版を復帰可能に保つ。
ユーザーは作業ブランチの送信とWindowsビルドを許可済み。mainのマージは今回の作業範囲外。
VRで見た目・血・接触・掴み・装備表示を確認し、既存リリース条件を満たしてから完成版を作る。

## 接続案内の参照

2026-10-11確認。UI名称はアプリの版で異なる場合がある。

- OpenAI公式アプリ案内: https://developers.openai.com/codex/app （現在の案内へ転送）
- MCP for Blender公式プロジェクトのQuickstart: https://www.mcp-for-blender.com/docs/quickstart
- Blender 4.5 Python API: https://docs.blender.org/api/4.5/
