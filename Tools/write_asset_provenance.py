"""Record the exact checked-out source and generated Windows asset bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--build', type=Path, default=Path('build'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        parser.error('--commit must be a full lowercase Git commit SHA')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if actual != args.commit:
        raise ValueError('Requested commit does not match the checkout')
    paths = subprocess.check_output([
        'git', 'ls-files', '-z', '--', 'Source/NIF', 'Source/Textures', 'Source/Audio',
        'Source/xEdit/build_plugin.py', 'Tests/test_plugin_binary.py',
        'Source/SKSE/HeadContactPlanes.hpp',
        'Source/SKSE/WeaponDimensions.hpp',
        'Tests/test_material_maps.py', 'Tools/write_asset_provenance.py',
        'Tools/package_visual_test.py', '.github/workflows/windows-nif-build.yml',
    ], cwd=root).decode('utf-8').split('\0')
    source = {path: sha256(root / path) for path in sorted(paths) if path}
    build = args.build.resolve()
    outputs = list(build.glob('meshes/**/*.nif')) + list(build.glob('textures/**/*.dds'))
    outputs += list(build.glob('sound/**/*.wav')) + list(build.glob('sound/**/audio_validation.json'))
    outputs += list(build.glob('textures/**/material_generation.json'))
    outputs += list(build.glob('textures/**/texture_validation.json'))
    outputs += [build / 'visual-preview/asset_manifest.json']
    outputs += [build / 'visual-preview/reference_mesh.cms']
    if not any(path.suffix == '.nif' for path in outputs) or not any(path.suffix == '.dds' for path in outputs):
        raise ValueError('Generated NIF and DDS files are required')
    data = {
        'schema_version': 1,
        'source_commit': args.commit,
        'source_files': source,
        'output_files': {path.relative_to(build).as_posix(): sha256(path) for path in sorted(outputs)},
    }
    target = build / 'ASSET_BUILD_PROVENANCE.json'
    target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(f'ASSET_PROVENANCE_PASS {len(source)} source files; {len(outputs)} output files; {args.commit}')


if __name__ == '__main__':
    main()
