"""Package one matched Windows visual/audio test build, never a combat release."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import math
import re
import struct
import zipfile


ROOT = Path(__file__).resolve().parents[1]
NIF_PATH = 'meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif'
TEXTURE_DIR = 'textures/weapons/ChainMorningstarVR'
VANILLA_TEXTURES = {'textures/cubemaps/shinydull_e.dds'}


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
    dll_sources = read_json(win / 'DLL_SOURCE_SHA256.json')
    dll_source_count = verify_sources({item['path']: item['sha256'] for item in dll_sources}, ROOT / 'Source/SKSE')
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
    require(len(dll) >= pe + 6 and dll[pe:pe + 4] == b'PE\0\0' and struct.unpack_from('<H', dll, pe + 4)[0] == 0x8664,
            'DLL must be Windows PE x64')
    nif = files[NIF_PATH]
    for name in ['CMS_ChainAnchor', 'CMS_HeadNode'] + [f'CMS_LinkNode_{i:02d}' for i in range(14)]:
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
    materials = read_json(assets / TEXTURE_DIR / 'material_generation.json')
    provenance = {
        'version': f'{version}-visual-test', 'source_commit': args.commit,
        'repository': 'https://github.com/ryutatsm/ChainMorningstarVR',
        'windows_dll_run': args.dll_run, 'windows_asset_run': args.asset_run,
        'windows_dll_artifact': args.dll_artifact, 'windows_asset_artifact': args.asset_artifact,
        'source_verification': {'dll_files': dll_source_count, 'asset_files': asset_source_count,
                                'text_line_endings': 'LF/CRLF normalized; binary input hashes exact'},
        'in_game_validated': False, 'native_head_contacts': False, 'equipment_drop_connected': False,
        'plugin_provenance': esp, 'asset_build_provenance': asset_provenance,
        'emblem': geometry['emblem'], 'material_generation': materials,
        'custom_texture_count': len(custom), 'vanilla_texture_dependencies': sorted(vanilla),
        'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in files.items()},
    }
    readme = f'''ChainMorningstarVR {version} — 外観・音のテスト版
ソース: {args.commit}

完成した戦闘MODではありません。Skyrim VR実機での起動・表示・音は未確認です。
鎖は表示用のシミュレーションです。壁・床・敵との物理接触、鉄球の実位置の
攻撃判定、頭／武器への命中時に装備を1/3で落とすゲーム内処理は未接続です。

変更: 新しい紋章画像を球面に沿う菱形台座へ割り当て、浅い浮き彫りを加えました。
提供された各部のテクスチャを加工し、鉄球・棘・鎖・金具・木・革・革紐へ使用。
片手メイス、攻撃44・重量17・価値550。エオルンドの商品追加を実装。

対象: Skyrim VR 1.4.15.0 / SKSEVR 2.0.12。
通常プレイと別のMODマネージャープロファイルで旧版を無効化してから、
このZIPをVortex/MO2でインストールし、ChainMorningstarVR.espを有効にします。
同名の古いDLL/NIF/テクスチャを混ぜず、SKSEVRで起動してください。
エオルンド販売、またはコンソール help "Chain Morningstar" 4 で確認できます。
FormID先頭はロード順で変わります。

右手または左手に1本ずつ装備し、紋章の湾曲、各部の質感、鎖の見た目と音を確認。
両手同時の2本には未対応。装備解除、メニュー、ロード、セル移動も確認します。
表示の揺れや通常のメイス攻撃は、この鉄球の物理攻撃が完成した証拠になりません。

確認結果とログは別添 ChainMorningstarVR-{version}-feedback-tools.zip で収集できます。
ゲーム終了後、解凍した Collect_CMS_Logs.cmd を実行してください。

Windows DLLとNIF/DDSは上記コミットのCI成果物を使用。
ESPはユーザー提供の原本を検証して生成。全ファイルのSHA-256は同梱。
Windows DLL CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.dll_run}
Windows NIF CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.asset_run}
'''
    game_file_count = len(files)
    files['README_Visual_Test_JA.txt'] = readme.encode('utf-8-sig')
    files['BUILD_PROVENANCE.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode('utf-8')
    args.out.mkdir(parents=True, exist_ok=True)
    archive = args.out / f'ChainMorningstarVR-{version}-visual-test.zip'
    write_zip(archive, files)
    feedback = args.out / f'ChainMorningstarVR-{version}-feedback-tools.zip'
    feedback_files = {name: (ROOT / 'Tools' / name).read_bytes() for name in ['Collect_CMS_Logs.cmd', 'Collect_CMS_Logs.ps1']}
    feedback_files['README_JA.txt'] = 'ゲーム終了後に解凍したCollect_CMS_Logs.cmdを実行。ゲームデータとセーブは変更しません。\n'.encode('utf-8-sig')
    write_zip(feedback, feedback_files)
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': sha(archive.read_bytes()), 'game_files': game_file_count,
                      'textures': len(custom), 'feedback': str(feedback)}, indent=2))


if __name__ == '__main__':
    main()
