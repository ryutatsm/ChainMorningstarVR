# Glamur同梱ReShadeのnull参照防止候補

2026-10-11に既存ログ`crash-2026-10-11-17-22-42.log`の
`dxgi.dll+011511B`、`RBX=0`、`mov rdx,[rbx]`への限定的な修正候補を作成・適用した。
ゲーム起動・反復CTD試験は行っていない。Actor・描画系の別例外の解消は未確認。

## 対象配布物

ローカルに保存されたGlamur Reshade VR 2.5.1の配布ZIP内DLLと、配置済みDLLが完全一致した。

- 配布ZIP SHA256: `80a21f8462ffbfc26944bf3e355ebc3843166ecdbefd1e8837e6d723005837fd`
- 元DLL SHA256: `da0f0736e80e73d6dcbc4400276df713c89b37c9dc6b7da0db3481898b7a177d`
- 表示版: `4.9.1.177 UNOFFICIAL`
- [Glamurの作者ページ](https://www.nexusmods.com/skyrimspecialedition/mods/61434)は
  元VRビルドを[fholger / The Sharper Eye](https://www.nexusmods.com/skyrimspecialedition/mods/46999)と記している。

この照合はソース全体の同定とは異なる。現在のDLLを保持した限定修正とし、
別版のビルドへ置き換えることはしない。

## 変更範囲

`VR_GetGenericInterface`内のRVA `0x1150CB`から`0x11511A`までの80バイトを置換する。
`sscanf`の結果確認後に`test rbx,rbx`と既存のreturn先への条件分岐を追加する。
取得失敗ではhookへ進まず、元の失敗結果とエラー値をそのまま呼び出し元へ返す。

空間確保のためhookスロットの設定を組み替える。先に`r8d=6`として上位ビットもゼロにし、
必要な版だけ`r8b=5`または`r8b=4`に変更する。各版のhook先・スロット番号は元と一致する。
既存関数の先頭、末尾、スタック操作、外部呼び出し、アンワインド情報は変えない。
新しい節やコード領域は追加せず、ファイルサイズ・イメージ配置も維持する。

PEチェックサムを再計算し、この値と80バイトの範囲以外は全バイト一致を検証した。
実際の変更バイト数は合計78。元ファイルには署名がないことも確認した。
入力のSHA256が異なる場合は処理を拒否する。元DLLへ直接パッチする生成ツールではない。

候補DLL SHA256: `db28f285b904c7eb8ba1a45753326a58c6f56a9e662694be3f33f4c8dad2b11c`

## 検証

[生成スクリプト](../Diagnostics/ReShade/patch_installed_build.py)と
[機械語の検証コード](../Diagnostics/ReShade/verify_binary_guard.py)を保存した。
Unicorn 2.1.4のx64 CPUで元と修正後の関数の機械語を実行する。
ログ出力、元APIの取得と呼び出し、sscanf、hook登録の外部関数を模擬する。
実際のDLLをOSへロードせず、OpenVR・Skyrim・GPUを起動しない。

- 3種類の配置アドレスで合計264条件を比較。
- 元のnull参照99条件は全て元の命令位置・アドレス0で再現し、修正後は失敗結果を返却。
- 元が正常に返る165条件は返却値・hook引数・エラー値が一致。
- 保存対象レジスターとスタックを復元し、元APIの呼び出し回数は1回。
- インターフェイス番号の境界、名前の不一致・空文字、エラー出力省略を含む。
- 元ハッシュが違う入力を拒否。

検証値・逆アセンブルは[検証JSON](../Diagnostics/ReShade/BINARY_GUARD_VERIFICATION.json)へ保存する。
これは関数とバイナリの検証であり、ゲーム全体の動作・描画やCTD全体の解消を保証しない。
参照取得が失敗した上流の理由も未確定である。

## 配布・適用・復元

候補と元へ戻すZIPをローカル成果物へ保存し、ReShadeのBSDライセンスと
crosire・fholger・rhellctのクレジットを添付した。公式リリースや作者による承認を意味しない。
ZIP内の`GameRoot/dxgi.dll`はSkyrimVR.exeと同じ場所用で、Data用のVortex MODではない。
ゲーム終了中に書き込み権限を得て22:58:22（日本時間）に直接適用し、配置後のハッシュを確認した。
元DLLは別に保存済み。戻す際はゲーム終了後に元のdxgi.dllへ復元する。
設定・シェーダー6ファイル、CMS・CHIMのDLL、CrashLogger設定は変更前と一致した。
配置・配布ハッシュは[適用記録](RESHade_BINARY_GUARD_DEPLOYMENT.json)に記載する。

ゲームは起動していない。新しいクラッシュログ・ダンプもなく、実機動作は未確認。
通常利用で得られる記録を解析対象とし、反復起動や意図的なCTD再現は依頼しない。
