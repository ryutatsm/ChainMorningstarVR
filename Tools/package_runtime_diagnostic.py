"""Build the explicitly requested audit4 runtime-test ZIP; never a completed release.

Uses the matched, already-built Windows DLL/assets. Their complete source
manifests must still match the checkout. Packaging docs/code have a separately
recorded commit, so publishing instructions cannot silently relabel a binary.
The normal release-candidate packager continues to reject audit builds.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import struct
import subprocess
import sys

from package_visual_test import (ROOT, NIF_PATH, TEXTURE_DIR, VANILLA_TEXTURES,
    MODEL_SCALE, LINK_COUNT, HEAD_REACH, require, sha, read_json, verify_sources,
    texture_references, check_dds, write_zip)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--windows-dir', type=Path, required=True)
    parser.add_argument('--plugin-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT.parent / 'output')
    for name in ['dll-run', 'asset-run', 'dll-artifact', 'asset-artifact']:
        parser.add_argument('--' + name, type=int, required=True)
    args = parser.parse_args()
    commit = args.source_commit
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Full Windows source commit required')
    packaging_commit = git('rev-parse', 'HEAD')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'Commit tracked edits before packaging')
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, packaging_commit], cwd=ROOT, check=True)
    version = '1.0.0-audit4'
    cmake = (ROOT / 'Source/SKSE/PluginSkeleton/CMakeLists.txt').read_text()
    require('project(ChainMorningstarVR VERSION 1.0.0' in cmake and
            'set(CMS_BUILD_LABEL "${PROJECT_VERSION}-audit4")' in cmake,
            'This diagnostic packager is restricted to audit4')
    win, assets = args.windows_dir, args.windows_dir / 'assets'
    asset_provenance = read_json(assets / 'ASSET_BUILD_PROVENANCE.json')
    require(asset_provenance['source_commit'] == commit, 'Asset source commit mismatch')
    asset_count = verify_sources(asset_provenance['source_files'], ROOT)
    for relative, expected in asset_provenance['output_files'].items():
        path = PurePosixPath(relative)
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe asset path')
        require(sha((assets / path).read_bytes()) == expected, 'Asset hash mismatch: ' + relative)
    dll_status = (win / 'BUILD_STATUS.txt').read_text(encoding='utf-8-sig')
    require(f'Commit: {commit}' in dll_status and f' {version} ' in dll_status and
            'investigation only -- RELEASE BLOCKED' in dll_status, 'Diagnostic DLL identity mismatch')
    dll_records = {r['path']: r['sha256'] for r in read_json(win / 'DLL_SOURCE_SHA256.json')}
    dll_root = ROOT / 'Source/SKSE'
    require(set(dll_records) == {p.relative_to(dll_root).as_posix() for p in dll_root.rglob('*')
        if p.is_file() and 'build' not in p.relative_to(dll_root).parts}, 'Incomplete DLL source set')
    dll_count = verify_sources(dll_records, dll_root)
    third = {r['path']: r['sha256'] for r in read_json(win / 'DLL_THIRD_PARTY_SHA256.json')}
    require(set(third) == {p.relative_to(ROOT).as_posix() for p in (ROOT / 'Source/ThirdParty').rglob('*')
        if p.is_file()}, 'Incomplete third-party source set')
    verify_sources(third, ROOT)
    for shared in ['HeadContactPlanes.hpp', 'WeaponDimensions.hpp']:
        require(shared in dll_records and 'Source/SKSE/' + shared in asset_provenance['source_files'],
                'Missing shared geometry source verification')
    subprocess.run([sys.executable, str(ROOT / 'Source/NIF/export_contact_planes.py'),
                    str(assets / 'visual-preview/reference_mesh.cms'), '--check'], cwd=ROOT, check=True)
    files = {
        'ChainMorningstarVR.esp': (args.plugin_dir / 'ChainMorningstarVR.esp').read_bytes(),
        'SKSE/Plugins/ChainMorningstarVR.dll': (win / 'SKSE/Plugins/ChainMorningstarVR.dll').read_bytes(),
        NIF_PATH: (assets / NIF_PATH).read_bytes(),
    }
    esp = read_json(args.plugin_dir / 'ChainMorningstarVR.provenance.json')
    require(sha(files['ChainMorningstarVR.esp']) == esp['plugin_sha256'], 'ESP provenance mismatch')
    name = 'チェーンドモーニングスター\0'.encode('utf-8')
    require(b'FULL' + struct.pack('<H', len(name)) + name in files['ChainMorningstarVR.esp'], 'Japanese FULL missing')
    dll = files['SKSE/Plugins/ChainMorningstarVR.dll']
    require(sha(dll) == (win / 'ChainMorningstarVR.dll.sha256').read_text(encoding='utf-8-sig').strip(), 'DLL hash mismatch')
    require(len(dll) >= 64 and dll[:2] == b'MZ', 'DLL DOS header missing')
    pe = struct.unpack_from('<I', dll, 60)[0]
    require(len(dll) >= pe + 26 and dll[pe:pe+4] == b'PE\0\0' and
            struct.unpack_from('<H', dll, pe+4)[0] == 0x8664 and
            struct.unpack_from('<H', dll, pe+24)[0] == 0x20b, 'Expected x64 Windows DLL')
    require(version.encode() in dll and b'heldMs=' in dll and b'chain-overextended' in dll and
            b'CMS head stability:' in dll and b'CMS native pose restored before sweep:' in dll and
            b'headTargets=' in dll and b'slot=' in dll and b'surface=' in dll and
            b'button=left-trigger' in dll and b'side-grip=unchanged' in dll and b'trigger-released' in dll,
            'Diagnostic runtime strings missing')
    nif = files[NIF_PATH]
    for node in ['BSInvMarker', 'CMS_ChainAnchor', 'CMS_HeadNode', 'BloodFX', 'BloodLighting'] + [f'CMS_LinkNode_{i:02d}' for i in range(LINK_COUNT)]:
        require(node.encode() in nif, 'Required NIF node missing: ' + node)
    custom, vanilla = texture_references(nif)
    require({p.lower() for p in vanilla} == VANILLA_TEXTURES, 'Vanilla dependency mismatch')
    actual = {p.relative_to(assets).as_posix().lower(): p for p in (assets / TEXTURE_DIR).glob('*.dds')}
    validations = {r['name'].lower(): r for r in read_json(assets / TEXTURE_DIR / 'texture_validation.json')}
    require(set(actual) == {p.lower() for p in custom}, 'NIF/DDS set mismatch')
    require(set(validations) == {PurePosixPath(p).name.lower() for p in custom}, 'DDS validation set mismatch')
    for path in sorted(custom):
        data = actual[path.lower()].read_bytes()
        check_dds(path, data, validations[PurePosixPath(path).name.lower()])
        files[path] = data
    for path, data in files.items():
        if path == NIF_PATH or path.lower().endswith('.dds'):
            require(asset_provenance['output_files'].get(path) == sha(data), 'Packaged asset provenance mismatch: ' + path)
    geometry = read_json(assets / 'visual-preview/asset_manifest.json')
    require(geometry['dimensions']['model_scale'] == MODEL_SCALE and
            geometry['dimensions']['chain_links'] == LINK_COUNT and
            abs(geometry['dimensions']['anchor_to_head_m'] - HEAD_REACH * MODEL_SCALE) < 1e-8,
            'Model/runtime dimensions mismatch')
    import math
    bounds = [math.floor(v) for v in geometry['bounds_skyrim_units'][0]] + [math.ceil(v) for v in geometry['bounds_skyrim_units'][1]]
    require(esp['bounds'] == bounds, 'ESP/model bounds mismatch')
    provenance = {
        'version': version, 'release_channel': 'runtime-diagnostic',
        'distribution_authorization': 'User requested this diagnostic package on 2026-10-07 JST',
        'source_commit': commit, 'packaging_commit': packaging_commit,
        'repository': 'https://github.com/ryutatsm/ChainMorningstarVR',
        'windows_dll_run': args.dll_run, 'windows_asset_run': args.asset_run,
        'windows_dll_artifact': args.dll_artifact, 'windows_asset_artifact': args.asset_artifact,
        'in_game_validated': False, 'completed_release': False,
        'source_verification': {'dll_files': dll_count, 'asset_files': asset_count,
            'third_party_files': len(third), 'native_contact_planes_match_nif_input': True,
            'text_line_endings': 'LF/CRLF normalized; binary hashes exact'},
        'audit3_runtime_observation': {'max_observed_hold_ms': 20119,
            'feedback_sha256': '32f1bab13d404b500e59eb308ee0c9b5dbaf640b961c093075c0e9194c2f8700',
            'warning_or_error_lines': 0, 'user_report': 'motion appears normal',
            'equipment_lottery_draws_observed': 0},
        'equipment_drop_scope': 'Enemy headgear and the struck hand held weapon/shield; not gauntlets',
        'equipment_drop_probability': 'one independent unbiased 1/3 draw per eligible contact episode',
        'grab_input': 'physical left index-finger trigger (OpenVR button 33)',
        'side_grip_binding': 'unchanged by CMS',
        'checks_requested': ['enemy worn headgear drop', 'right-hand equipped weapon drop',
            'left-hand weapon/shield drop', 'one roll during sustained contact',
            'dual-wield and two-handed ownership', 'exact enchantment/tempering retained'],
        'dimensions': geometry['dimensions'], 'plugin_provenance': esp,
        'asset_build_provenance': asset_provenance,
        'vanilla_texture_dependencies': sorted(vanilla),
        'files': {p: {'bytes': len(data), 'sha256': sha(data)} for p, data in files.items()},
    }
    game_count = len(files)
    test_readme = (ROOT / 'Docs/DIAGNOSTIC_TEST_AUDIT4_JA.txt').read_text()
    files['README_JA.txt'] = test_readme.encode('utf-8-sig')
    files['DIAGNOSTIC_STATUS.md'] = (ROOT / 'Docs/EQUIPMENT_DROP_AUDIT4.md').read_bytes()
    files['LICENSES/HIGGS_GPL-3.0.txt'] = (ROOT / 'Source/ThirdParty/HIGGS/LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.txt'] = (
        'HIGGS interface and documented native integration adapted from HIGGS by adamhynek.\n'
        'GPL-3.0; see LICENSES/HIGGS_GPL-3.0.txt. CommonLib type adaptation preserves interface order.\n'
        'Upstream: https://github.com/adamhynek/higgs/tree/93bf67b1bc4c4a11a20ccaef0d5012781d0d7eee\n'
        f'Exact runtime source: https://github.com/ryutatsm/ChainMorningstarVR/tree/{commit}\n'
    ).encode()
    files['BUILD_PROVENANCE.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2)+'\n').encode()
    files['SHA256SUMS.txt'] = ''.join(f'{sha(data)}  {p}\n' for p, data in sorted(files.items())).encode()
    args.out.mkdir(parents=True, exist_ok=True)
    archive = args.out / f'ChainMorningstarVR-{version}-diagnostic.zip'
    write_zip(archive, files)
    feedback_files = {p: (ROOT/'Tools'/p).read_bytes() for p in ['Collect_CMS_Logs.cmd', 'Collect_CMS_Logs.ps1']}
    feedback_files['README_JA.txt'] = (ROOT/'Tools/Feedback_README_JA.txt').read_text(encoding='utf-8-sig').encode('utf-8-sig')
    feedback_files['TEST_STEPS_JA.txt'] = test_readme.encode('utf-8-sig')
    feedback = args.out / f'ChainMorningstarVR-{version}-feedback-tools.zip'
    write_zip(feedback, feedback_files)
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
        'sha256': sha(archive.read_bytes()), 'game_files': game_count,
        'feedback': str(feedback), 'packaging_commit': packaging_commit,
        'runtime_commit': commit, 'completed_release': False}, indent=2))


if __name__ == '__main__':
    main()
