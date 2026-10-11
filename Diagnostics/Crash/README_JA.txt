既存CrashLoggerログの読み取り専用分類

実行例（リポジトリ内、Python 3.10以降）:
python Diagnostics/Crash/classify_existing_logs.py --log-dir <保存済みログのフォルダー> --output <別のJSONファイル>

検証:
python -m unittest discover -s Diagnostics/Crash -p "test_*.py" -v

ゲーム起動、MODの有効／無効切替、セーブ編集、ネットワーク送信は行いません。
例外位置だけでなく、対象EXEのMD5、レジスタ、[P]付きのコールスタックを照合します。
Actor終了経路の分類は「ユーザーが手動終了した」「原因MODが分かった」という意味ではありません。
分類できないログはunclassifiedとし、別環境へ既知の位置を流用しません。
CHIM／ReShadeの既知位置分類は位置の一致だけで、DLLビルドの同一性や修正後の挙動を判定しません。
出力は入力ファイル名・ハッシュ・位置・分類のみで、セーブ内容・個人名・フルログは含めません。

詳細: Docs/CRASH_TRIAGE_20261011_JA.md の「ゲーム本体の命令との照合」。
ゲーム本体の復号実装・全逆アセンブル・個人ログはこのフォルダーに含めません。

保存済みメモリダンプの読み取り（追加ツール）

python Diagnostics/Crash/inspect_saved_minidump.py <保存が終わった.dmpファイル> --output <新しいJSONファイル>

これは保存済みファイルの解析だけを行います。ゲームへの接続・起動・常駐・自動監視はしません。
大きなファイルを読み取り専用のメモリマップで開き、必要な小さい領域だけを取り出します。
Memory64ListとMemoryList、AMD64の例外コンテキストに対応します。
別の実行ファイル、別アーキテクチャ、命令の不一致では既知のゲーム用フィールドを解釈しません。
ただし、画像サイズ・ビルド時刻・命令照合は実行ファイル全体の同一性証明ではありません。

Mist Menuの既知位置なら、所有者候補／VRMenuSceneのvtable、問題のノード参照、
既知フレームの保存値を記録します。Actorの既知位置ならshadowSceneNode[0]を記録します。
メモリ未収録と、記録されたnullを区別します。候補のvtableが一致しても生存中とは断定しません。
終了処理の判定には別のテキストログ分類と照合が必要です。
過去の書き込み履歴や割り当て寿命、原因MODを自動特定するツールではありません。
既存JSONへの上書きは拒否します。出力や元ダンプはローカルで保持し、公開リポジトリへ入れないでください。

検証済み範囲:
・合成ダンプによる読み取り・境界・不足メモリ・CLI非上書きの13テスト
・既存ログ分類の7テスト（計20件）
・専用の無害なPython子プロセスをWindows APIでダンプ化し、Memory64Listの実データ読み取りを確認
・ゲームの実ダンプ、ゲーム内互換性、CTD解消は未確認

構造の出典（Microsoft公式）:
https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_memory64_list
https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_module
https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_stream
https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-context
