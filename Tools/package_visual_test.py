"""Package a matched Windows release candidate with explicit runtime evidence limits."""
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
    project_version = re.search(r'project\(ChainMorningstarVR VERSION ([0-9.]+)', cmake).group(1)
    suffix = re.search(r'set\(CMS_BUILD_LABEL \"\$\{PROJECT_VERSION\}(-[a-z0-9]+)\"\)', cmake).group(1)
    version = project_version + suffix
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == args.commit,
            'Package commit differs from current checkout')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT),
            'Tracked source files must be committed before packaging')
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
    require('release candidate -- RUNTIME GATES PENDING' in dll_status, 'DLL artifact is not the release candidate')
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
    japanese_name = 'チェーンドモーニングスター\0'.encode('utf-8')
    require(b'FULL' + struct.pack('<H', len(japanese_name)) + japanese_name in files['ChainMorningstarVR.esp'],
            'ESP Japanese display name is missing')
    nif = files[NIF_PATH]
    require(b'BSInvMarker' in nif, 'NIF inventory marker is missing')
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
        'version': version, 'release_channel': 'candidate', 'source_commit': args.commit,
        'repository': 'https://github.com/ryutatsm/ChainMorningstarVR',
        'windows_dll_run': args.dll_run, 'windows_asset_run': args.asset_run,
        'windows_dll_artifact': args.dll_artifact, 'windows_asset_artifact': args.asset_artifact,
        'source_verification': {'dll_files': dll_source_count, 'asset_files': asset_source_count,
                                'third_party_files': third_party_source_count,
                                'native_contact_planes_match_nif_input': True,
                                'text_line_endings': 'LF/CRLF normalized; binary input hashes exact'},
        'in_game_validated': False,
        'runtime_evidence': read_json(ROOT / 'Docs/RUNTIME_EVIDENCE_100_RC2.json'),
        'native_head_contacts': True, 'equipment_drop_connected': True,
        'chain_link_registered_bodies': False,
        'chain_link_collision_queries': {'enabled': True, 'shape': 'swept capsule per link',
            'registered_attack_bodies': False, 'damage': False, 'equipment_drop': False,
            'response': 'one-way: chain bends/slides; no force applied to objects or NPCs'},
        'head_motion': {'mass_kg': 12, 'damping_per_90hz': .990, 'restitution': .025},
        'display_name': 'チェーンドモーニングスター',
        'inventory_marker': {'rotation_milliradians': [4712, 0, 0], 'zoom': 1.0},
        'offhand_head_grip': {'input': 'physical left grip while right hand equips CMS',
            'hold': 'two endpoints with native world contact priority', 'empty_left_hand_required': True,
            'higgs_two_hand_conflict_fix': 'thread-local HIGGS Update CustomPick2 selection exclusion',
            'higgs_settings_changed': False, 'physical_collision_filters_changed': False},
        'player_chain_contacts': {'source': '11 capsules from visible VRIK skeleton',
            'continuous_relative_sweep': True, 'registered_bodies': False, 'damage': False},
        'dimensions': geometry['dimensions'], 'weapon_blood': geometry['blood'],
        'head_impact_sound': {'layers': [
            {'impact_data': 'Skyrim.esm:0009150E', 'name': 'PHYBodyMetalLargeImpact',
             'selection': 'sound2 (loud), fallback sound1', 'volume': '0.75 + 0.25 * intensity'},
            {'impact_data': 'Skyrim.esm:0004BB53', 'name': 'WPNBluntVsMetalImpact',
             'selection': 'sound1, fallback sound2', 'volume': '0.48 + 0.18 * intensity'}],
            'overlapping_impact_pairs': 4, 'minimum_impulse_kg_mps': 3.0, 'cooldown_s': .22},
        'physics_status': 'release candidate; see bundled release status for pending target checks',
        'runtime_requirements': {'Skyrim VR': '1.4.15.0', 'SKSEVR': '2.0.12',
                                 'HIGGS': '1.6.0 or newer (interface001)',
                                 'PLANCK': 'required for NPC physical contacts and melee damage'},
        'plugin_provenance': esp, 'asset_build_provenance': asset_provenance,
        'emblem': geometry['emblem'], 'material_generation': materials,
        'custom_texture_count': len(custom), 'vanilla_texture_dependencies': sorted(vanilla),
        'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in files.items()},
    }
    readme = (ROOT / 'Docs/INSTALL_VR.md').read_text(encoding='utf-8')
    readme += f'\nソース: {args.commit}\nWindows DLL CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.dll_run}\nWindows NIF CI: https://github.com/ryutatsm/ChainMorningstarVR/actions/runs/{args.asset_run}\n'
    game_file_count = len(files)
    files['README_JA.txt'] = readme.encode('utf-8-sig')
    files['FINAL_CHECK_JA.txt'] = (ROOT / 'Docs/FINAL_CHECK_JA.txt').read_text(encoding='utf-8').encode('utf-8-sig')
    files['RELEASE_STATUS.md'] = (ROOT / 'Docs/RELEASE_STATUS_100_RC2.md').read_bytes()
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
    archive = args.out / f'ChainMorningstarVR-{version}.zip'
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
