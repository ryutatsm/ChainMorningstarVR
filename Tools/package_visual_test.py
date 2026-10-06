"""Package one matched Windows physics test build; in-game behavior is unverified."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
NIF_PATH = 'meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif'
TEXTURE_DIR = 'textures/weapons/ChainMorningstarVR'
VANILLA_TEXTURES = {'textures/cubemaps/shinydull_e.dds', 'textures/cubemaps/eyecubemap.dds',
                    'textures/blood/bloodhitdecals01.dds', 'textures/blood/bloodhitdecals01add.dds',
                    'textures/blood/bloodhitdecals01_n.dds'}
sys.path.insert(0, str(ROOT / 'Source/NIF'))
from weapon_dimensions import MODEL_SCALE, LINK_COUNT, HEAD_REACH


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def verify_sources(records, base):
    """Allow Git's Windows text checkout conversion; binary inputs must be exact."""
    require(bool(records), 'Empty source provenance')
    for relative, expected in records.items():
        path = PurePosixPath(relative)
        require(not path.is_absolute() and '..' not in path.parts, f'Unsafe source path: {relative}')
        data = (base / path).read_bytes()
        candidates = {sha(data)}
        try:
            data.decode('utf-8')
            if b'\0' not in data:
                lf = data.replace(b'\r\n', b'\n')
                candidates.update((sha(lf), sha(lf.replace(b'\n', b'\r\n'))))
        except UnicodeDecodeError:
            pass
        require(expected in candidates, f'Source hash mismatch: {relative}')
    return len(records)


def texture_references(nif):
    refs = {match.decode('ascii').replace('\\', '/') for match in
            re.findall(rb'textures[\\/][A-Za-z0-9_ ./\\-]+\.dds', nif, re.IGNORECASE)}
    require(refs, 'NIF contains no readable DDS references')
    custom, vanilla = set(), set()
    for path in refs:
        require('..' not in PurePosixPath(path).parts, f'Unsafe texture path: {path}')
        if path.lower() in VANILLA_TEXTURES:
            vanilla.add(path)
        else:
            require(path.lower().startswith(TEXTURE_DIR.lower() + '/'), f'Unexpected external texture: {path}')
            custom.add(path)
    require(custom and vanilla, 'Expected custom textures and the vanilla cubemap')
    return custom, vanilla


def check_dds(path, data, validation):
    require(len(data) >= 128 and data[:4] == b'DDS ' and data[84:88] == b'DXT5', f'Invalid DXT5 DDS: {path}')
    height, width = struct.unpack_from('<II', data, 12)
    levels = struct.unpack_from('<I', data, 28)[0]
    require(width > 0 and height > 0 and levels == math.floor(math.log2(max(width, height))) + 1,
            f'Incomplete mip chain: {path}')
    size = 128 + sum(max(1, (max(1, width >> level) + 3) // 4) *
                     max(1, (max(1, height >> level) + 3) // 4) * 16 for level in range(levels))
    require(len(data) == size, f'DDS byte count does not match all mips: {path}')
    require(validation['sha256'] == sha(data) and validation['bytes'] == len(data), f'DDS validation hash mismatch: {path}')
    require(validation['size'] == [width, height] and validation['format'] == 'DXT5', f'DDS validation format mismatch: {path}')
    require(validation['mip_levels'] == levels and validation['decoded_mips'] == levels, f'DDS mips were not all decoded: {path}')


def write_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f'ZIP CRC failure: {path}')
        for name, data in files.items():
            require(archive.read(name) == data, f'ZIP byte mismatch: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--version', help='Defaults to the CMake project version; must match it')
    parser.add_argument('--dll-run', type=int, required=True)
    parser.add_argument('--asset-run', type=int, required=True)
    parser.add_argument('--dll-artifact', type=int, required=True)
    parser.add_argument('--asset-artifact', type=int, required=True)
    parser.add_argument('--windows-dir', type=Path, default=ROOT / 'build/windows-ci')
    parser.add_argument('--plugin-dir', type=Path, default=ROOT / 'build/plugin')
    parser.add_argument('--out', type=Path, default=ROOT.parent / 'output')
    args = parser.parse_args()
    require(re.fullmatch(r'[0-9a-f]{40}', args.commit), 'A full lowercase source commit is required')
    cmake = (ROOT / 'Source/SKSE/PluginSkeleton/CMakeLists.txt').read_text()
    version = re.search(r'project\(ChainMorningstarVR VERSION ([0-9.]+)', cmake).group(1)
    require(args.version is None or args.version == version, '--version differs from the CMake project')
    win, assets = args.windows_dir, args.windows_dir / 'assets'
    asset_provenance = read_json(assets / 'ASSET_BUILD_PROVENANCE.json')
    require(asset_provenance['source_commit'] == args.commit, 'Windows asset commit mismatch')
    asset_source_count = verify_sources(asset_provenance['source_files'], ROOT)
    for relative, expected in asset_provenance['output_files'].items():
        path = PurePosixPath(relative)
        require(not path.is_absolute() and '..' not in path.parts, f'Unsafe artifact path: {relative}')
        require(sha((assets / path).read_bytes()) == expected, f'Windows asset hash mismatch: {relative}')
    dll_status = (win / 'BUILD_STATUS.txt').read_text(encoding='utf-8-sig')
    require(f'Commit: {args.commit}' in dll_status and f' {version} ' in dll_status, 'Windows DLL commit/version mismatch')
    require('physics test -- NOT A RELEASE' in dll_status, 'DLL artifact is not the physics test build')
    dll_sources = read_json(win / 'DLL_SOURCE_SHA256.json')
    dll_records = {item['path']: item['sha256'] for item in dll_sources}
    dll_root = ROOT / 'Source/SKSE'
    expected_dll_sources = {path.relative_to(dll_root).as_posix() for path in dll_root.rglob('*')
                            if path.is_file() and 'build' not in path.relative_to(dll_root).parts}
    require(set(dll_records) == expected_dll_sources, 'DLL source provenance does not cover the complete runtime')
    dll_source_count = verify_sources(dll_records, dll_root)
    third_party = read_json(win / 'DLL_THIRD_PARTY_SHA256.json')
    third_party_records = {item['path']: item['sha256'] for item in third_party}
    require(set(third_party_records) == {path.relative_to(ROOT).as_posix()
            for path in (ROOT / 'Source/ThirdParty').rglob('*') if path.is_file()},
            'DLL third-party source provenance is incomplete')
    third_party_source_count = verify_sources(third_party_records, ROOT)
    header = 'Source/SKSE/HeadContactPlanes.hpp'
    cms_path = 'visual-preview/reference_mesh.cms'
    require(header in asset_provenance['source_files'] and 'HeadContactPlanes.hpp' in dll_records,
            'Native contact planes must be covered by both asset and DLL source provenance')
    require('Source/SKSE/WeaponDimensions.hpp' in asset_provenance['source_files'] and
            'WeaponDimensions.hpp' in dll_records, 'Shared dimensions missing from paired build provenance')
    require(cms_path in asset_provenance['output_files'], 'NIF collision source missing from asset provenance')
    subprocess.run([sys.executable, str(ROOT / 'Source/NIF/export_contact_planes.py'),
                    str(assets / cms_path), '--check'], check=True, cwd=ROOT)
    files = {
        'ChainMorningstarVR.esp': (args.plugin_dir / 'ChainMorningstarVR.esp').read_bytes(),
        'SKSE/Plugins/ChainMorningstarVR.dll': (win / 'SKSE/Plugins/ChainMorningstarVR.dll').read_bytes(),
        NIF_PATH: (assets / NIF_PATH).read_bytes(),
    }
    esp = read_json(args.plugin_dir / 'ChainMorningstarVR.provenance.json')
    require(sha(files['ChainMorningstarVR.esp']) == esp['plugin_sha256'], 'ESP provenance hash mismatch')
    dll = files['SKSE/Plugins/ChainMorningstarVR.dll']
    require(sha(dll) == (win / 'ChainMorningstarVR.dll.sha256').read_text(encoding='utf-8-sig').strip(), 'DLL checksum mismatch')
    require(len(dll) >= 64 and dll[:2] == b'MZ', 'DLL DOS header missing')
    pe = struct.unpack_from('<I', dll, 60)[0]
    require(len(dll) >= pe + 26 and dll[pe:pe + 4] == b'PE\0\0'
            and struct.unpack_from('<H', dll, pe + 4)[0] == 0x8664
            and struct.unpack_from('<H', dll, pe + 24)[0] == 0x20b,
            'DLL must be Windows PE x64')
    nif = files[NIF_PATH]
    for name in ['CMS_ChainAnchor', 'CMS_HeadNode', 'BloodFX', 'BloodLighting'] + [f'CMS_LinkNode_{i:02d}' for i in range(LINK_COUNT)]:
        require(name.encode() in nif, f'Required NIF node absent: {name}')
    custom, vanilla = texture_references(nif)
    actual = {path.relative_to(assets).as_posix().lower(): path for path in (assets / TEXTURE_DIR).glob('*.dds')}
    require(set(actual) == {path.lower() for path in custom}, 'Emitted DDS set differs from actual NIF texture references')
    texture_validation = read_json(assets / TEXTURE_DIR / 'texture_validation.json')
    validations = {item['name'].lower(): item for item in texture_validation}
    require(set(validations) == {PurePosixPath(path).name.lower() for path in custom}, 'DDS validation set differs from NIF references')
    for name in sorted(custom):
        data = actual[name.lower()].read_bytes()
        check_dds(name, data, validations[PurePosixPath(name).name.lower()])
        files[name] = data
    for name, data in files.items():
        if name == NIF_PATH or name.lower().endswith('.dds'):
            require(asset_provenance['output_files'].get(name) == sha(data), f'Packaged asset absent from CI provenance: {name}')
    geometry = read_json(assets / 'visual-preview/asset_manifest.json')
    require(geometry['dimensions']['model_scale'] == MODEL_SCALE and
            geometry['dimensions']['chain_links'] == LINK_COUNT and
            abs(geometry['dimensions']['anchor_to_head_m'] - HEAD_REACH * MODEL_SCALE) < 1e-8,
            'Generated model dimensions differ from the runtime')
    expected_bounds = ([math.floor(v) for v in geometry['bounds_skyrim_units'][0]] +
                       [math.ceil(v) for v in geometry['bounds_skyrim_units'][1]])
    require(esp['bounds'] == expected_bounds, 'ESP bounds do not match the resized model')
    require({p.lower() for p in vanilla} == VANILLA_TEXTURES, 'Missing vanilla blood material dependencies')
    materials = read_json(assets / TEXTURE_DIR / 'material_generation.json')
    provenance = {
        'version': f'{version}-physics-test', 'source_commit': args.commit,
        'repository': 'https://github.com/ryutatsm/ChainMorningstarVR',
        'windows_dll_run': args.dll_run, 'windows_asset_run': args.asset_run,
        'windows_dll_artifact': args.dll_artifact, 'windows_asset_artifact': args.asset_artifact,
        'source_verification': {'dll_files': dll_source_count, 'asset_files': asset_source_count,
                                'third_party_files': third_party_source_count,
                                'native_contact_planes_match_nif_input': True,
                                'text_line_endings': 'LF/CRLF normalized; binary input hashes exact'},
        'in_game_validated': False, 'native_head_contacts': True, 'equipment_drop_connected': True,
        'chain_link_registered_bodies': False,
        'chain_link_collision_queries': {'enabled': True, 'shape': 'swept capsule per link',
            'registered_attack_bodies': False, 'damage': False, 'equipment_drop': False,
            'response': 'one-way: chain bends/slides; no force applied to objects or NPCs'},
        'head_motion': {'mass_kg': 12, 'damping_per_90hz': .990, 'restitution': .025},
        'dimensions': geometry['dimensions'], 'weapon_blood': geometry['blood'],
        'head_impact_sound': {'impact_data': 'Skyrim.esm:0005CEFB', 'name': 'PHYGenericMetalHeavyImpact',
            'selection': 'sound2 (loud), fallback sound1', 'minimum_impulse_kg_mps': 3.0, 'cooldown_s': .22},
        'physics_status': 'implemented test paths; Windows build validation is not in-game proof',
        'runtime_requirements': {'Skyrim VR': '1.4.15.0', 'SKSEVR': '2.0.12',
                                 'HIGGS': '1.6.0 or newer (interface001)',
                                 'PLANCK': 'required for NPC physical contacts and melee damage'},
        'plugin_provenance': esp, 'asset_build_provenance': asset_provenance,
        'emblem': geometry['emblem'], 'material_generation': materials,
        'custom_texture_count': len(custom), 'vanilla_texture_dependencies': sorted(vanilla),
        'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in files.items()},
    }
    readme = f'''ChainMorningstarVR {version} — 物理・装備落下のテスト版
ソース: {args.commit}

0.8.0変更: 柄・鎖・鉄球・棘・紋章と当たり判定を従来の75％へ縮小。
鎖は5個追加して14→19個。同じ大きさ・間隔・物理と接触処理を追加分にも適用。
鉄球が物体や人にぶつかると標準の重金属衝突音を再生。鎖音とは別の音です。
鉄球・棘・紋章の表面に沿った血メッシュを追加。ゲーム標準の武器流血で表示されます。
血が出ない接触、鎖だけの接触、壁への衝突から独自に血を生成する処理はありません。
鎖だけの接触はダメージも装備落下の抽選も発生させません。
鉄球の12kg設定、低反発・減衰と、0.7.0の黒い素材・凹凸・曲面紋章を維持。
同じ75％サイズの14リンク版より鎖が約24.2cm長くなります（VRIK等の倍率適用前）。

0.7.0についてユーザーから正常動作の報告があります。
0.8.0の追加機能と戦闘・安定性は実機未確認です。正式リリースではありません。
鉄球と棘の複合衝突形状をHIGGSの武器剛体へ設定し、物理ステップ直前に実位置へ
反映します。接触情報を鎖のシミュレーションへ戻す処理を接続しました。
敵の頭部／装備中の武器への確認済み接触から、対応する装備を1/3の確率で
外して落とす処理を接続しています。接触が続く間の重複抽選を抑制します。
鎖は接触に合わせて曲がり、滑る方式です。鎖から物体やNPCを押す力は加えません。
鎖の輪は穴を埋めたカプセル近似で、リンク同士の衝突や物体への巻き付け拘束はありません。

球面に沿った紋章と、提供画像から加工した各部位の材質を引き継いでいます。
片手メイス、攻撃44・重量17・価値550。エオルンドの商品追加を実装。

対象: Skyrim VR 1.4.15.0 / SKSEVR 2.0.12。
物理機能にはHIGGS 1.6.0以上、NPCとの物理接触とダメージにはPLANCKが必要です。
依存MODが不足した状態は、物理機能の動作確認にはなりません。
通常プレイと別のMODマネージャープロファイルで旧版を無効化してから、
このZIPをVortex/MO2でインストールし、ChainMorningstarVR.espを有効にします。
同名の古いDLL/NIF/テクスチャを混ぜず、SKSEVRで起動してください。
エオルンド販売、またはコンソール help "Chain Morningstar" 4 で確認できます。
FormID先頭はロード順で変わります。

片手だけに1本を装備し、右手と左手をそれぞれ確認してください。両手同時の2本は未対応。
まず抜刀し、その場で腕だけを15秒動かして柄の追従と鎖の揺れを確認します。
次に床・壁で鉄球が止まるか、敵の胴への命中で装備が落ちないか、頭／装備武器への
独立した命中でのみ該当装備が落ちるかを確認します。1/3は各独立接触の確率で、
3回ごとに必ず1回という意味ではありません。武器の空白部分への近接は命中に含めません。
装備解除、メニュー、ロード、セル移動後に古い接触が再利用されないことも確認します。
攻撃力やNPCの衝突はPLANCKの設定にも影響されます。

今回の重点確認:
1. 装備して75％の大きさと19個の鎖を確認。追加分まで揺れ、球につながるか確認。
2. 鉄球側の追加した鎖も机の縁・壁・敵の腕へ当て、曲がって離れるか確認。
3. 鎖だけではダメージ・装備落下が起きないことを確認。
4. 鉄球を壁・床・物体・敵に当て、重い金属音が鳴るか確認。床に置いた状態では連打しないこと。
5. 敵への命中で血が出た後、球・棘・紋章に血が沿い、球の動きに追従するか確認。
6. 血のない新品で壁へ当て、血が出ないことを確認。流血オフ設定では血は表示されません。
7. 解除・再装備・メニュー・ロード・セル移動で動作と音に異常が出ないか確認。
ログの Chain collision queries active と chainContacts は鎖処理の動作確認に使えます。

確認結果とログは別添 ChainMorningstarVR-{version}-feedback-tools.zip で収集できます。
ゲーム終了後、解凍した Collect_CMS_Logs.cmd を実行してください。

Windows DLLとNIF/DDSは上記コミットのCI成果物を使用。
ESPはユーザー提供の原本を検証して生成。全ファイルのSHA-256は同梱。
Windows DLL CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.dll_run}
Windows NIF CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.asset_run}
'''
    game_file_count = len(files)
    files['README_Physics_Test_JA.txt'] = readme.encode('utf-8-sig')
    files['LICENSES/HIGGS_GPL-3.0.txt'] = (ROOT / 'Source/ThirdParty/HIGGS/LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.txt'] = (
        'HIGGS interface declarations and documented native integration are adapted from HIGGS by adamhynek.\n'
        'HIGGS upstream: https://github.com/adamhynek/higgs/tree/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee\n'
        'See LICENSES/HIGGS_GPL-3.0.txt. Adaptation preserves interface order and uses CommonLib types.\n'
        f'Exact build source: https://github.com/ryutatsm/ChainMorningstarVR/tree/{args.commit}\n'
    ).encode('utf-8')
    files['BUILD_PROVENANCE.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode('utf-8')
    args.out.mkdir(parents=True, exist_ok=True)
    archive = args.out / f'ChainMorningstarVR-{version}-physics-test.zip'
    write_zip(archive, files)
    feedback = args.out / f'ChainMorningstarVR-{version}-feedback-tools.zip'
    feedback_files = {name: (ROOT / 'Tools' / name).read_bytes() for name in ['Collect_CMS_Logs.cmd', 'Collect_CMS_Logs.ps1']}
    feedback_files['README_JA.txt'] = (ROOT / 'Tools/Feedback_README_JA.txt').read_text(encoding='utf-8-sig').encode('utf-8-sig')
    write_zip(feedback, feedback_files)
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': sha(archive.read_bytes()), 'game_files': game_file_count,
                      'textures': len(custom), 'feedback': str(feedback)}, indent=2))


if __name__ == '__main__':
    main()
