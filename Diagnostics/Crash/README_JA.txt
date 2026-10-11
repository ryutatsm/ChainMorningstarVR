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
