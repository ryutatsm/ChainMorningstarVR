"""Make a NIF-only Vortex test overlay. Requires the unchanged audit6 base MOD.

This is deliberately not a completed release, DLL build or texture exporter.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from cms_io import load, sha256

BASE_ZIP_SHA256='63c6a4afaa5d032f58b66e4ce13c41f3ef410df8d19c15ee5714614d835bcd70'
NIF_PATH='meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif'
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cms',type=Path,required=True)
    p.add_argument('--baseline-cms',type=Path,required=True)
    p.add_argument('--baseline-zip',type=Path,required=True)
    p.add_argument('--writer',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if sha256(a.baseline_zip.read_bytes())!=BASE_ZIP_SHA256: raise ValueError('Wrong audit6 base ZIP')
    original=load(a.baseline_cms)
    edited=load(a.cms,require_baseline=False)
    report_path=a.cms.with_suffix('.edit.json')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    if report['edited_cms_sha256']!=sha256(a.cms.read_bytes()): raise ValueError('CMS/report mismatch')
    if original['nodes']!=edited['nodes'] or original['hulls']!=edited['hulls']:
        raise ValueError('Physics/node contract changed')
    if [(m['name'],m['parent'],m['material'],m['faces'],len(m['vertices'])) for m in original['meshes']] != [(m['name'],m['parent'],m['material'],m['faces'],len(m['vertices'])) for m in edited['meshes']]:
        raise ValueError('Topology/material contract changed')
    with ZipFile(a.baseline_zip) as z: base_nif=z.read(NIF_PATH)
    # A stale writer may parse successfully but silently lose audit6 metadata.
    with tempfile.TemporaryDirectory(prefix='cms-writer-check-') as check_dir:
        check_nif=Path(check_dir)/'baseline.nif'
        subprocess.run([str(a.writer.resolve()),str(a.baseline_cms.resolve()),str(check_nif)],check=True)
        if check_nif.read_bytes()!=base_nif:
            raise ValueError('NIF writer does not reproduce audit6; rebuild pinned source before packaging')
    subprocess.run([sys.executable,str(ROOT/'Source/NIF/export_contact_planes.py'),str(a.cms.resolve()),'--check'],cwd=ROOT,check=True)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    nif=a.out.with_suffix('.nif')
    subprocess.run([str(a.writer.resolve()),str(a.cms.resolve()),str(nif.resolve())],check=True)
    report['nif_sha256']=sha256(nif.read_bytes())
    report['baseline_nif_sha256']=sha256(base_nif)
    report['nif_identical_to_baseline']=nif.read_bytes()==base_nif
    report['baseline_zip_sha256']=BASE_ZIP_SHA256
    report['nif_writer_sha256']=sha256(a.writer.read_bytes())
    report['nif_writer_source_sha256']=sha256((ROOT/'Source/NIF/export_reference_nif.cpp').read_bytes())
    report['nif_writer_baseline_reproduction_verified']=True
    report['kind']='visual-test-overlay-requires-audit6'
    files={NIF_PATH:nif.read_bytes(),
           'BLENDER_EDIT_PROVENANCE.json':(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode(),
           'README_BLENDER_TEST_JA.txt':('Blender外観確認用の上書きMODです。単独では動作しません。\n'
            'audit6本体を有効にしたまま、VortexでこのZIPを導入し、競合時はこのMODを後に読み込んでください。\n'
            'DLL・ESP・テクスチャ・音声はaudit6本体を使用します。正式完成版ではありません。\n'
            '元に戻すときはこの外観確認MODだけを無効化し、配置を更新してください。\n').encode('utf-8')}
    files['SHA256SUMS_BLENDER_EDIT.txt']=''.join(sha256(v)+'  '+k+'\n' for k,v in sorted(files.items())).encode()
    with ZipFile(a.out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()): z.writestr(name,data)
    print('VISUAL_OVERLAY_PASS',a.out,'NIF identical:',report['nif_identical_to_baseline'])


if __name__=='__main__': main()
