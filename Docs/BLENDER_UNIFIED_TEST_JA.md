# audit6 統合・外観テスト版

ユーザーの「このMODを一本化して」の指示により、最新の革の縁を修正した3,996三角形モデルとaudit6本体を1つのVortex用ZIPにまとめる。mainへの統合や正式完成版の公開は行わない。

## 導入

1. Skyrim VRを終了する。
2. Vortexで旧`ChainMorningstarVR-1.0.0-audit6-diagnostic`と以前の外観テストをすべて無効化する。
3. `ChainMorningstarVR-1.0.0-audit6-unified-3996-test.zip`をファイルからインストールし、有効にする。
4. `ChainMorningstarVR.esp`を有効にし、「MODを配置」を実行する。
5. 既存のSKSEVR、HIGGSなどの前提MODは引き続き有効にし、通常のSKSEVR起動方法で確認する。

この統合版に別のaudit6本体は不要。DLL、ESP、武器の登録ID、音声はaudit6とバイト同一で、内部バージョン表示もaudit6のまま。元本体と外観テストを重ねた構成と、配置されるゲーム用27ファイルは完全に一致する。一本化自体による追加のFPS改善や物理演算の変更はない。

旧MODと元ZIPは動作確認までバックアップとして残せる。統合版の動作が確認できたら旧MODを削除してよい。戻す場合は統合版を無効化し、元audit6本体を再有効化して配置する。以前の外観に戻す場合は、該当する外観テスト1つを本体の後に配置する。

## 入力と保護

- `Assets/Audit6Baseline/ChainMorningstarVR-1.0.0-audit6-diagnostic.zip`は元ZIPのバイト同一コピー。SHA256は`63c6a4afaa5d032f58b66e4ce13c41f3ef410df8d19c15ee5714614d835bcd70`。
- `Assets/BlenderFinish/UNIFIED_PAYLOAD_SHA256.json`は置換を許可するNIF1個とDDS4枚のハッシュを固定する。DLLやESPが外観入力に入っている場合や、承認したファイルが変わった場合は停止する。
- 表示用2,900、血用1,096、合計3,996三角形。31表示メッシュ、22ランタイムノード、19鎖節、15衝突形状、21画像を維持する。
- 元のモデル生成スクリプトは呼ばない。保存済みCMSとDDSから安全確認付きエクスポーターと固定NIF writerで外観を再生成し、本体の5ファイルだけを置換する。
- 元の入力メタデータはZIP内`Provenance/`に歴史的記録として保管する。現在の統合内容はルートの`README_JA.txt`、`BUILD_PROVENANCE.json`、`SHA256SUMS.txt`に記録する。

## 再生成

Windows CIの`Authored Blender unified test (audit6)`が固定writerで外観ZIPを生成した後、以下を実行する。ローカルでは同じ引数のoverlayに検証済みの外観ZIPを指定できる。

```powershell
python Tests/test_unified_package.py --baseline-zip Assets/Audit6Baseline/ChainMorningstarVR-1.0.0-audit6-diagnostic.zip --overlay build/blender-finish-overlay/ChainMorningstarVR-audit6-leather-edge-test.zip --inputs Assets/BlenderFinish/UNIFIED_PAYLOAD_SHA256.json
python Tools/Blender/package_unified_test.py --baseline-zip Assets/Audit6Baseline/ChainMorningstarVR-1.0.0-audit6-diagnostic.zip --overlay build/blender-finish-overlay/ChainMorningstarVR-audit6-leather-edge-test.zip --inputs Assets/BlenderFinish/UNIFIED_PAYLOAD_SHA256.json --out build/blender-finish-overlay/ChainMorningstarVR-1.0.0-audit6-unified-3996-test.zip
```

元ZIP・全ファイルのSHA256、全ゲーム用バイトの等価性、ZIP CRC、ESPのモデル/武器値/音声参照、x64 DLL、NIFのテクスチャ参照、DDSの形式/ミップを検証する。異なる本体、DLLの混入、未承認NIF、欠落、誤った三角形数、パス逸脱などを拒否する統合テストも実行する。

この統合テスト版のSkyrim VR実機、FPS、xEdit Check for Errors、掴み、血、摩擦、装備解除、音は未確認。バイト同一性を実機動作確認の代わりに扱わない。DLLを新しくビルドした版ではなく、検証対象のaudit6 DLLをそのまま同梱する。
