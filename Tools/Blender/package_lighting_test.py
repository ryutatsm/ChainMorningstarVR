"""Complete Vortex test MOD with a byte-bounded dark-lighting correction."""
import argparse
import json
import subprocess
from pathlib import Path
import package_unified_test as unified
from nif_material_contract import patch, OWN_EMIT, ENVMAP_LIGHT_FADE


def inspect(path, inspector):
    return json.loads(subprocess.check_output([str(inspector.resolve()), str(path.resolve())]))


def verify_inspections(before, after):
    unified.require(before['node_count'] == after['node_count'] == 22, 'Runtime nodes changed')
    unified.require(len(before['shapes']) == len(after['shapes']) == 33, 'Shapes changed')
    visible = 0
    for original, edited in zip(before['shapes'], after['shapes']):
        if original['name'] in ('BloodFX', 'BloodLighting'):
            unified.require(original == edited, 'Blood material changed')
            continue
        unified.require(edited['flags1'] == original['flags1'] | OWN_EMIT, 'Own black emittance missing')
        unified.require(edited['flags2'] == original['flags2'] | ENVMAP_LIGHT_FADE, 'Lighting-dependent reflection missing')
        unified.require(edited['emissive'] == [0, 0, 0] and edited['emissive_multiple'] == 0, 'Nonzero emission')
        protected = set(original) - {'flags1', 'flags2', 'emissive_multiple'}
        unified.require({k: original[k] for k in protected} == {k: edited[k] for k in protected}, 'Other material field changed')
        visible += 1
    unified.require(visible == 31, 'Incomplete independent material check')


def contact_readme():
    return (
        'チェーンドモーニングスター audit6 統合・スパイク接合修正版（3,996三角形）\n\n'
        'DLL・ESP・音声・21 DDSを含む、Vortexに単独で導入できる統合テスト版です。前回の暗所照明修正も含みます。\n'
        'SKSEVR・HIGGS・PLANCK等の前提MODは引き続き必要です。\n\n'
        '導入:\n'
        '1. Skyrim VRを終了します。\n'
        '2. Vortexで現在のunified-lighting-test版、統合3996版、旧audit6-diagnostic本体、以前の外観テストをすべて無効化します。\n'
        '3. ChainMorningstarVR-1.0.0-audit6-unified-spike-contact-test.zipを「ファイルからインストール」し、この版だけを有効にします。\n'
        '4. ChainMorningstarVR.espを有効にし、「MODを配置」を実行します。\n'
        '5. 通常のSKSEVR起動方法でゲームを再起動してください。以前から所持していた武器にも同じモデルが反映されます。\n\n'
        '修正内容:\n'
        '軽量化で省略したスパイク下部と鉄球の平らな面の間に、根元の隙間が残っていました。\n'
        '14本の既存底面をそれぞれの軸に沿って約6.3～9.5mm内側へ延ばし、底面全体を実際の鉄球メッシュ内部に入れました。\n'
        '鉄球を構成する全224面の平面から最低0.35mm内側に底面を収め、頂点だけでなく底面の辺・内部も接合を検証しています。\n'
        '追加三角形は0。表示2,900＋血用1,096＝3,996三角形を維持。スパイク先端、根元の幅、UV、法線、鉄球本体、エンブレムは維持。\n'
        '他の30表示メッシュ、22ノード、19鎖節、15衝突形状、75%寸法と原点・階層は維持。\n'
        '血用2形状は修正後のスパイクに沿うよう固定NIF writerで再生成しています。\n'
        '前回の暗所照明設定を維持。21 DDSとDLL・ESP・音声は前回統合版とバイト同一です。\n'
        '内部バージョン表示は1.0.0-audit6のままです。物理演算・音・掴み等のコード変更はありません。\n\n'
        '検証:\n'
        '同じカメラ・照明のBlender比較、保存ファイルからの安全確認付き書き出し、14本の接合検査、NIF再読込、ZIP CRC・全ファイルSHA256を確認。\n'
        '実機画像の加工による変更後画像は作成していません。Blender画像は形状比較であり、ゲームの照明再現ではありません。\n'
        '今回版のSkyrim VR実機、xEdit、FPS、血・掴み・摩擦・装備解除・音は未確認。正式完成版ではありません。\n\n'
        '確認してほしい点:\n'
        '同じ持ち方で鉄球を回し、全方向のスパイク根元に背景の見える隙間がないか確認してください。暗所・明所で材質、血の付き方も確認してください。\n\n'
        '戻し方:\n'
        '今回のスパイク接合版を無効化し、直前のunified-lighting-test統合版を再有効化して「MODを配置」、ゲームを再起動します。\n'
        '確認が終わるまで旧版ZIP/MODは残してください。統合版を複数同時に有効化しないでください。\n'
    ).encode('utf-8-sig')


def package(a):
    commit = a.packaging_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=unified.ROOT, text=True).strip()
    files, old = unified.compose(a.baseline_zip.read_bytes(), a.overlay.read_bytes(), json.loads(a.inputs.read_text()), commit)
    previous_game = unified.game_files(files)
    corrected, proof = patch(files[unified.NIF])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    nif = a.out.with_suffix('.nif')
    source = a.out.with_suffix('.before.nif')
    source.write_bytes(files[unified.NIF]); nif.write_bytes(corrected)
    before, after = inspect(source, a.inspector), inspect(nif, a.inspector)
    verify_inspections(before, after)
    files[unified.NIF] = corrected
    unified.require({n for n in previous_game if previous_game[n] != files[n]} == {unified.NIF}, 'Only NIF may differ from previous unified game payload')
    unified.runtime_checks(files)
    files.pop('SHA256SUMS.txt')
    files['Provenance/UNIFIED_SOURCE_CONFIGURATION.json'] = files.pop('BUILD_PROVENANCE.json')
    files['Provenance/LIGHTING_MATERIAL_CHANGES.json'] = (json.dumps(proof, indent=2) + '\n').encode()
    files['README_JA.txt'] = (
        'チェーンドモーニングスター audit6 統合・暗所照明テスト版（3,996三角形）\n\n'
        '本体DLL・ESP・音声・全テクスチャを含む、単独で導入できる統合版です。\n'
        '前提のSKSEVR・HIGGS・PLANCK等は引き続き必要です。元audit6本体や別の外観テストを重ねる必要はありません。\n\n'
        '導入:\n'
        '1. Skyrim VRを終了します。\n'
        '2. Vortexで前回の統合3996テスト版、旧audit6本体、以前の外観テストをすべて無効化します。\n'
        '3. 今回のunified-lighting-test.zipをファイルからインストールし、この統合版だけを有効にします。\n'
        '4. ChainMorningstarVR.espを有効にし、「MODを配置」を実行します。\n'
        '5. 通常のSKSEVR起動方法でゲームを再起動します。以前から所持していた武器にも反映されます。\n\n'
        '原因調査と修正:\n'
        '導入済みNIFは前回配布版とSHA256が一致しました。発光色は黒ですが、標準の鉄・鋼メイスと異なりOwn EmitとEnvMap Light Fadeが欠けていました。\n'
        '31表示材質すべてで、自身の発光色を黒・強度0に固定し、環境反射を照明に応じて弱める設定にしました。\n'
        '暗所で明るさが残る原因候補に対応した、小さなシェーダー修正です。実際の改善はゲーム内で比較してください。\n'
        '変更はNIF内の124バイトだけ。21DDS、黒鉄・木・革の色と凹凸、エンブレム、反射強度・光沢値は変更していません。\n'
        '形状・UV・法線・接線・22ノード・19鎖節・15衝突形状・血用形状もバイト同一です。総三角形は3,996のままです。\n'
        'DLL・ESP・音声はaudit6と同じで、内部バージョン表示も1.0.0-audit6のままです。\n\n'
        '比較:\n'
        '添付画像と同じ暗い場所で、同じ位置・視線・持ち方・照明で見比べてください。明るい屋外や松明の近くでも材質感を確認してください。\n'
        '今回のゲーム内照明、FPS、xEdit、掴み・血・摩擦・装備解除・音の実機確認は未実施です。正式完成版ではありません。\n\n'
        '戻す:\n'
        '今回の暗所照明テスト版を無効化し、前回のunified-3996-test統合版を再有効化して配置・再起動します。\n'
        '旧版は確認が終わるまで残してください。両方の統合版を同時に有効化しないでください。\n'
    ).encode('utf-8-sig')
    visual=json.loads(files['Provenance/VISUAL_EDIT_SOURCE.json'])
    contact=visual.get('spike_contact_finish')
    if contact:files['README_JA.txt']=contact_readme()
    report = dict(old)
    report.update(format='cms-audit6-unified-lighting-test-v1', version='1.0.0-audit6-unified-lighting-test',
                  release_channel='unified-lighting-test', all_game_files_equal_to_prior_base_plus_overlay=False,
                  all_game_files_equal_to_previous_unified_except_nif=True, previous_unified_user_reported_success=True,
                  lighting_material_patch=proof, independent_nifly_material_inspection_verified=True,
                  nif_sha256=unified.sha(corrected), texture_files_changed=0,
                  package_lighting_tool_sha256=unified.sha(Path(__file__).read_bytes()),
                  material_patch_tool_sha256=unified.sha(Path(__file__).with_name('nif_material_contract.py').read_bytes()),
                  files={n:dict(bytes=len(v), sha256=unified.sha(v)) for n,v in sorted(files.items())})
    if contact:
        report.update(format='cms-audit6-unified-spike-contact-test-v1',
                      version='1.0.0-audit6-unified-spike-contact-test',release_channel='unified-spike-contact-test',
                      spike_contact_finish=contact,
                      previous_unified_success_is_historical=True,
                      previous_user_success_build='unified-3996-test',
                      lighting_patch_preserves_geometry_relative_to_current_contact_nif=True)
    files['BUILD_PROVENANCE.json'] = (json.dumps(report, indent=2) + '\n').encode()
    files['SHA256SUMS.txt'] = ''.join(unified.sha(v) + '  ' + n + '\n' for n,v in sorted(files.items())).encode()
    unified.write_zip(a.out, files)
    report.update(zip_sha256=unified.sha(a.out.read_bytes()), zip_bytes=a.out.stat().st_size,
                  zip_crc_and_internal_hashes_verified=True)
    a.out.with_suffix('.provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    a.out.with_suffix('.inspection.json').write_text(json.dumps(dict(before=before, after=after), indent=2) + '\n')
    print('UNIFIED_CONTACT_TEST_PASS' if contact else 'UNIFIED_LIGHTING_TEST_PASS', a.out, '124 shader bytes; 27 game files; unchanged 3996 triangles', report['zip_sha256'])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-zip', 'overlay', 'inputs', 'inspector', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--packaging-commit')
    package(parser.parse_args())
