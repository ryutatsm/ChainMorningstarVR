"""Verify committed Blender-finish snapshots before rebuilding the visual overlay."""
import argparse,json,sys
from pathlib import Path
from cms_io import load,sha256
from package_optimized_visuals import check_cms,TEXTURES


def validate(directory):
    manifest=json.loads((directory/'INPUT_SHA256.json').read_text())
    expected={'ChainMorningstarVR_work.blend','optimized.cms','optimized.edit.json','audit6_baseline.cms'}|{
        'textures/'+name for name in TEXTURES}
    if set(manifest['files'])!=expected:raise ValueError('Unexpected input set')
    for name,digest in manifest['files'].items():
        if sha256((directory/name).read_bytes())!=digest:raise ValueError('Input hash mismatch: '+name)
    cms=load(directory/'optimized.cms',require_baseline=False);baseline=load(directory/'audit6_baseline.cms')
    report=json.loads((directory/'optimized.edit.json').read_text())
    check_cms(cms,baseline,report)
    if report['saved_blend_sha256']!=manifest['files']['ChainMorningstarVR_work.blend']:raise ValueError('Blend/proof mismatch')
    # Opening a file with enabled Blender add-ons can set is_dirty immediately.
    # Require the independent CLI export from disk rather than guessing why.
    if not report['source_loaded_from_saved_file']:raise ValueError('Snapshot needs a fresh CLI export from disk')
    for texture in report['texture_bakes']:
        if manifest['files']['textures/'+texture['name']]!=texture['sha256']:raise ValueError('Texture/proof mismatch')
    print('OPTIMIZED_INPUTS_PASS',len(expected),'hashed inputs',report['after_triangles'],'triangles')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    validate(p.parse_args().directory)
