ReShade OpenVRのnull参照：ソース差分と部品検証

対象は既存ログの dxgi.dll+011511B、RBX=0、命令 48 8b 13。
配置DLLの同じ位置で、VR_GetGenericInterfaceの戻り値を確認せず
compositorのvtableへ進むことを逆アセンブルで確認した。
devbench 1.19.0のkInputLoadedからGetIVRCompositorへの経路もログと一致する。
これはVRインターフェイスが取得できなかった上流の理由まで確定するものではない。

公開fholger/reshadeのopenvr_alpha2コミット
cd4b5350e61ee949dfffab3ef97b6c8054ced1ff の実際の関数本体をoriginal.incへ抽出し、
null確認を1条件追加したものをpatched.incとした。
SOURCE_EVIDENCE.jsonのソースSHA256はUTF-8/LFに正規化して計算している。

MSVC x64 Native Tools環境で次を実行できる。
  cl /nologo /std:c++17 /EHsc /W4 /WX /D_CRT_SECURE_NO_WARNINGS /utf-8 regression.cpp
  regression.exe
出力先は作業用ディレクトリーに変更してよい。
CRTの非推奨警告のみ抑制し、元ソースのsscanf呼び出しをそのまま検証する。

8ケース：取得失敗、compositorの022/009/008/007、非対応006、
非compositor、nullの非compositorと省略されたエラー出力。
模擬vtable関数がnull入力を例外として検出する。
元コードの失敗と修正後の安全な失敗返却、および正常時の対象・hook位置を確認する。
OpenVR本体やSkyrimを起動する試験ではない。

重要な限界
配置DLLは4.9.1.177 UNOFFICIALである。公開ビルドスクリプト上、末尾177は
ローカルのReleaseビルド回数であり、Gitのコミットを識別する値ではない。
配置DLLのソース全体との対応は証明できていない。
ここまでのソース差分は再現と修正案の記録であり、ソースからの代替DLLはビルドしていない。
後続調査では同一DLLを含む配布ZIPが見つかり、配置DLLの作業コピーへ限定的な修正を行った。
その別経路の検証・適用状況は ../../Docs/RESHade_BINARY_GUARD_JA.md を参照。
CMS本体には変更を加えていない。

公式側でも同種のnull確認が追加されている（別の版・別の入口）。
https://github.com/crosire/reshade/commit/ef20c520fdc5a7d904bb0c0442ce9063d777d166
これだけで現在の描画構成全体の更新を互換性確認済みとは扱わない。

配置DLLに限定した修正候補（別経路）
patch_installed_build.py はGlamur 2.5.1同梱DLLのSHA256が一致する場合だけ処理する。
入力は変更せず、80バイトの分岐領域とPEチェックサムだけを修正した別ファイルを生成する。
ソース全体の同定を待たずに描画コードを保つためのバイナリ修正で、新版への更新ではない。
同じバージョン番号でもSHA256が異なるDLLへは適用しない。

必要なPythonパッケージ: pefile、capstone、unicorn==2.1.4。
実行例（入力はゲームフォルダー外へ保存した元DLLのコピーを使う）:
  python verify_binary_guard.py --original original/dxgi.dll --output-dir candidate
出力には修正候補DLLと検証JSONを含む。元DLLをロード・実行しない。
実際の関数の機械語をUnicornのx64 CPU内で実行し、外部APIは模擬する。
ゲーム全体の互換性・描画の試験ではない。

264条件中、元のnull参照99条件を再現し、修正後は返却できた。
元が失敗しない165条件では、返却値・hook引数・エラー値・保存レジスター・スタックが一致した。
3種類の配置アドレス、インターフェイス番号の境界、取得失敗、エラー出力省略も含む。
再配布する場合はReShadeのBSDライセンスと、crosire・fholger・rhellctのクレジットを添える。
