# 鉄球とスパイクの根元接合 — 3,996三角形の統合テスト版

2026-10-11 18:01:26の実機画像でスパイク根元が浮いて見えるとの指示に対応する。直前の革の縁修正版CMSを固定入力にして、14本の底面リングのみを鉄球内部へ延ばす。根元の幅・先端・UV・カスタム法線と面数を保持する。Booleanや追加リメッシュは行わない。

`Tools/Blender/contracts/spike_contact_source.cms`のSHA256は`76e945ab472b49e233eb5931270768f95381222158c5b16321cecbaeef556a2b`。`spike_contact_contract.py`はこの入力から許可する修正を独立に算出する。14本の底面を元の軸方向へ約6.325〜9.532mm延長し、実際の鉄球の全224三角形の外向き平面に対して最低0.35mm内側へ収める。半空間の交差は凸なので、底面頂点がすべて内側なら底面の辺・内部もすべて内側となる。閉じた鉄球表面も検査する。理想球の半径だけを使った接触判定ではない。

## 安全確認経路

これは元audit6の微変形エクスポーターの2mm範囲、および軽量化エクスポーターの元表面に対する6mm範囲を超える意図的な根元補修なので、専用の固定入力契約を追加した。全体の許容差を広げず、スパイク1メッシュの底面リングの軸方向延長だけを10mm以内で許可する。他の30表示メッシュは直前CMSと完全同一でなければ拒否する。

`export_under4k_visuals.py`は保存済みBlenderを独立に開き、専用契約、元の法線向き・UV向き・位相、ノード・原点・単位・衝突・外周bounds、21内蔵画像と4焼き込みPNGを検査する。スパイクの距離欄だけは固定された接合後表面を基準とし、元audit6表面との距離も`original_audit6_distances`に別途保存する。元表面との差を6mm以下だったと主張しない。他部位の6mm規則は維持する。

Blenderが変形時に再符号化するカスタム法線は、観測した最大成分差約0.00009に限って受け付ける。形状・UVは1e-7m以内の一致を要求する。検証後、書き出すスパイク法線・UVと継ぎ目インデックスを固定元入力へ正規化し、座標は実際のBlender頂点から取る。NIF用CMSの先端・法線・UV・面は元入力と完全同一を要求する。

革の縁の旧証明は3,980→3,996三角形への歴史的な工程記録として保持する。現在の他部位不変は今回のスパイク契約が証明し、革の接合形状自体も独立に再検査する。

```powershell
& $BlenderExe --background --python Tools/Blender/finish_spike_contacts.py -- --blend SOURCE.blend --out build/blender-work/Blender/ChainMorningstarVR_spike_contact_work.blend
& $BlenderExe --background --python Tools/Blender/export_under4k_visuals.py -- --blend build/blender-work/Blender/ChainMorningstarVR_spike_contact_work.blend --textures Assets/BlenderFinish/textures --out build/spike-contact/optimized.cms
```

`finish_spike_contacts.py`のSOURCEには固定元CMSに対応する直前の革の縁修正版Blenderを指定する。完成済み接合版への二重適用は対象外。旧作業ファイルを保持する。

## NIF・照明・統合

固定niflyのwriterで元audit6 NIFをSHA256まで完全再現してから新しいCMSを変換する。血用2形状は修正後の鉄球・スパイク・エンブレムから再生成し、法線オフセット0.225mmを再読込で検証する。

- 表示2,900、血用1,096、合計3,996三角形。追加三角形0。
- 31表示メッシュ、22ノード、19鎖節、15衝突形状。75%寸法・先端・全体boundsを維持。
- CMS SHA256: `bd33532f40971f1af144b81c9a94b22d7a92d80875a68b109e13069b81005243`。
- 照明適用前NIF: `dfabd8dd383eb063bc3f61a4af0cde7a3760badef9e79d386b82125318ca2e65`。
- 配布用の照明維持NIF: `8d07faf527074902495386f0e9c8a2b8e53ffd8b0e9d33f27c401f8656a2302f`。

既存の暗所照明修正（Own Emit、黒・発光強度0、EnvMap Light Fade）を同じ124バイト限定経路で適用する。入力NIFのSHA256は今回の修正モデルで再固定し、前回材質の再現試験は別名の固定プロファイルだけで許可する。`test_spike_nif_diff.py`は前回CMSから前回照明NIFを再現し、今回との変更ブロックがスパイク・BloodFX・BloodLightingの3つだけであることを確認する。ノード・衝突・全材質・他形状・ヘッダー・フッターはバイト同一。全21 DDS、DLL、ESP、3音声も保持する。

`UNIFIED_PAYLOAD_SHA256.json`は入力を全hashで固定する。`visual_input_commit=packaging-commit`は保存済み入力と包装コードが同じコミットにあることを示す明示マーカーで、最終provenanceにはその実際の40桁Git SHAを記録する。未確定文字列を配布記録に残さない。

Windows CIは保存済み入力だけを読む専用経路で変換・接合・保護バイト・照明・統合ZIPを検証する。元モデル生成CIのブランチ除外を維持し、Blender編集を上書きしない。単独導入用成果物は`ChainMorningstarVR-1.0.0-audit6-unified-spike-contact-test.zip`。

## 比較と実機確認

Blenderの変更前後は同じカメラ行列・照明・96サンプル・seed 1744・AgXで比較した。実機の変更後画像は加工・生成していない。今回MCPの初期化がタイムアウトしたため、保存ファイルをBlender 4.5.2本体でバックグラウンド検証した。別の開いているシーンには触れていない。

`test_blender_under4k.py`は21不正入力と繰り返し書き出しを確認する。`test_spike_contacts.py`は専用契約と独立した原点レイ／三角形交差の方式で、14根元の全辺をそれぞれ65点で検査する。同じ試験を実際のNIFをniflyで再読込した座標にも適用する。

ゲームを終了し、直前の統合照明版と旧本体・外観テストを無効にして今回の統合ZIPだけを有効化する。ESPを有効にし、Vortexで配置して再起動する。所持済み武器にも同じ参照先のモデルが適用される。戻す場合は今回版を無効化し、直前のunified-lighting-test統合版を再有効化・配置・再起動する。

今回の実機、xEdit、FPS、掴み、血、摩擦、装備解除、音の検証は未実施。前回のユーザーによる成功報告は歴史的記録であり、今回の検証済み表示へ流用しない。mainへの統合・正式公開は行わない。
