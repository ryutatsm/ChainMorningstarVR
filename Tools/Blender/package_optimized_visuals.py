"""Build a four-DDS/NIF Vortex overlay from guarded Blender optimization inputs.

The immutable baseline NIF hash is an independent writer check, so CI needs no
private artifact download. With --baseline-zip, additionally verify the user's
complete audit6 installation archive and compare its actual NIF bytes.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cms_io import load,sha256
from package_visual_edit import BASE_ZIP_SHA256,NIF_PATH,ROOT
sys.path.insert(0,str(ROOT/'Source/Textures'))
from encode_dds import encode

BASE_NIF_SHA256='648aa99090d81e9b8067a0965f1066e166509d3003a61e881fbae9d48264dc87'
CORD='CMS_CMS_ROOT_cord'
TEXTURES={'cms_leather_d.png','cms_leather_n.png','cms_wood_n.png','cms_emblem_n.png'}


def check_cms(cms,baseline,report):
    under4k=report['format']=='cms-blender-under4k-v2'
    if not under4k and report['format']!='cms-blender-optimized-v1':raise ValueError('Wrong export route')
    limit=6. if under4k else .15
    if under4k:
        draw=sum(len(m['faces']) for m in cms['meshes'])
        blood=2*sum(len(m['faces']) for m in cms['meshes'] if m['name'] in ('CMS_CMS_HeadNode_metal','CMS_CMS_HeadNode_spike','CMS_CMS_HeadNode_emblem'))
        if draw+blood>4000 or report['nif_total_triangles']!=draw+blood or report['blood_triangles']!=blood:
            raise ValueError('Inclusive 4000 triangle budget exceeded or proof inconsistent')
        if report['triangle_budget_including_blood']!=4000 or not report['hidden_emblem_backing_removed'] or not report['hidden_spike_bases_removed']:
            raise ValueError('Explicit hidden-surface omission policy changed')
    if report['edited_cms_sha256']!=sha256(cms['data']):raise ValueError('CMS/report mismatch')
    if cms['nodes']!=baseline['nodes'] or cms['hulls']!=baseline['hulls']:raise ValueError('Physics/node contract changed')
    if ''.join(cms['lines'][cms['collision_start']:])!=''.join(baseline['lines'][baseline['collision_start']:]):raise ValueError('Hull bytes changed')
    expected=[m for m in baseline['meshes'] if m['name']!=CORD]
    if [(m['name'],m['parent'],m['material']) for m in expected]!=[(m['name'],m['parent'],m['material']) for m in cms['meshes']]:
        raise ValueError('Only the named cord may be removed; no mesh/material/parent additions')
    if len(report['meshes'])!=31 or report['mesh_count']!=31 or report['chain_links']!=19 or report['removed_mesh']!=CORD:
        raise ValueError('Wrong optimization contract')
    if report['surface_limit_mm']!=limit:raise ValueError('Surface tolerance changed')
    for original,edited,proof in zip(expected,cms['meshes'],report['meshes']):
        rows=np.array(edited['vertices']);old=np.array(original['vertices'])
        faces=np.array(edited['faces'])
        if proof['mesh']!=edited['name'] or proof['after_triangles']!=len(faces) or proof['before_triangles']!=len(original['faces']):
            raise ValueError('Mesh/count proof mismatch')
        if len(faces)>len(original['faces']) or not 0<len(rows)<65536 or not 0<len(faces)<65536:raise ValueError('Index/count contract')
        if not np.isfinite(rows).all() or np.any(abs(np.linalg.norm(rows[:,3:6],axis=1)-1)>.0001):raise ValueError('Invalid vertex/normal')
        if faces.min()<0 or faces.max()>=len(rows):raise ValueError('Invalid index')
        bounds_margin=.0015 if under4k else 1e-7
        if np.any(rows[:,:3].min(0)<old[:,:3].min(0)-bounds_margin) or np.any(rows[:,:3].max(0)>old[:,:3].max(0)+bounds_margin):
            raise ValueError('Bounds expanded')
        area=np.cross(rows[faces[:,1],:3]-rows[faces[:,0],:3],rows[faces[:,2],:3]-rows[faces[:,0],:3])
        if np.any(np.linalg.norm(area,axis=1)<1e-13):raise ValueError('Degenerate triangle')
        if min(proof['minimum_face_normal_dot'],1)<=0:raise ValueError('Inverted surface')
        if not proof['uv_orientation_verified']:raise ValueError('Missing UV orientation proof')
        if max(d['max_mm'] for d in proof['distances'].values())>limit+.00001:raise ValueError('Surface error')
    if sum(len(m['faces']) for m in cms['meshes'])!=report['after_triangles']:raise ValueError('Total count mismatch')
    if report.get('spike_contact_finish'):
        from spike_contact_contract import validate_cms
        if validate_cms(cms)!=report['spike_contact_finish']:raise ValueError('Spike root contact proof mismatch')
        from leather_edge_contract import validate_rows,LEATHER
        leather=next(m for m in cms['meshes'] if m['name']==LEATHER)
        if validate_rows(leather['vertices'],leather['faces'])!=report['leather_edge_finish']:raise ValueError('Retained leather proof mismatch')
    elif report.get('leather_edge_finish'):
        from leather_edge_contract import validate_cms
        if validate_cms(cms)!=report['leather_edge_finish']:raise ValueError('Leather edge contact proof mismatch')


def package(a):
    baseline=load(a.baseline_cms);cms=load(a.cms,require_baseline=False)
    report=json.loads(a.cms.with_suffix('.edit.json').read_text())
    if not report.get('source_loaded_from_saved_file'):raise ValueError('Need an independent CLI export from the saved project')
    check_cms(cms,baseline,report)
    if report['saved_blend_sha256']!=sha256(a.blend.read_bytes()):raise ValueError('Saved blend/report mismatch')
    if {t['name'] for t in report['texture_bakes']}!=TEXTURES:raise ValueError('Unexpected DDS set')
    base_nif=None
    if a.baseline_zip:
        if sha256(a.baseline_zip.read_bytes())!=BASE_ZIP_SHA256:raise ValueError('Wrong audit6 ZIP')
        with ZipFile(a.baseline_zip) as z:base_nif=z.read(NIF_PATH)
        if sha256(base_nif)!=BASE_NIF_SHA256:raise ValueError('Wrong audit6 NIF')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cms-opt-writer-',dir=a.cms.resolve().parent) as tmp:
        check=Path(tmp)/'baseline.nif'
        subprocess.run([str(a.writer.resolve()),str(a.baseline_cms.resolve()),str(check)],check=True)
        if sha256(check.read_bytes())!=BASE_NIF_SHA256 or (base_nif is not None and check.read_bytes()!=base_nif):
            raise ValueError('Writer does not reproduce audit6 exactly')
    subprocess.run([sys.executable,str(ROOT/'Source/NIF/export_contact_planes.py'),str(a.cms.resolve()),'--check'],cwd=ROOT,check=True)
    nif=a.out.with_suffix('.nif')
    subprocess.run([str(a.writer.resolve()),str(a.cms.resolve()),str(nif.resolve())],check=True)
    files={NIF_PATH:nif.read_bytes()};checks=[]
    for texture in report['texture_bakes']:
        path=a.textures/texture['name']
        if sha256(path.read_bytes())!=texture['sha256']:raise ValueError('PNG/proof mismatch')
        im=Image.open(path);im.load()
        if im.mode!='RGBA' or im.size!=(1024,1024):raise ValueError('Wrong texture format')
        checks.append(encode(path))
        dds=path.with_suffix('.dds')
        files['textures/weapons/ChainMorningstarVR/'+dds.name]=dds.read_bytes()
    report.update(nif_sha256=sha256(nif.read_bytes()),baseline_nif_sha256=BASE_NIF_SHA256,
                  baseline_zip_sha256=BASE_ZIP_SHA256,nif_writer_sha256=sha256(a.writer.read_bytes()),
                  nif_writer_source_sha256=sha256((ROOT/'Source/NIF/export_reference_nif.cpp').read_bytes()),
                  nif_writer_baseline_reproduction_verified=True,
                  kind='optimized-visual-test-overlay-requires-audit6',dds_validation=checks,
                  base_dll_esp_audio_unchanged=True,blood_regenerated_by_pinned_writer=True)
    tool_paths=['Tools/Blender/optimize_audit6.py','Tools/Blender/surface_contract.py',
                'Tools/Blender/export_optimized_visuals.py','Tools/Blender/package_optimized_visuals.py',
                'Source/Textures/encode_dds.py']
    if report['format']=='cms-blender-under4k-v2':
        tool_paths+=['Tools/Blender/retopologize_under4k.py','Tools/Blender/export_under4k_visuals.py']
    if report.get('leather_edge_finish'):
        tool_paths+=['Tools/Blender/finish_leather_edges.py','Tools/Blender/leather_edge_contract.py',
                     'Tools/Blender/contracts/leather_edge_source.cms']
    if report.get('spike_contact_finish'):
        tool_paths+=['Tools/Blender/finish_spike_contacts.py','Tools/Blender/spike_contact_contract.py',
                     'Tools/Blender/contracts/spike_contact_source.cms']
    report['tool_source_sha256']={name:sha256((ROOT/name).read_bytes()) for name in tool_paths}
    import PIL
    report['texture_encoder_versions']=dict(pillow=PIL.__version__,numpy=np.__version__)
    a.out.with_suffix('.provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    files['OPTIMIZED_VISUAL_PROVENANCE.json']=(json.dumps(report,indent=2)+'\n').encode()
    files['README_OPTIMIZED_TEST_JA.txt']=('チェーンドモーニングスター audit6 軽量化・外観テストMOD\n'
       '単独では動作しません。audit6本体を有効にしたままVortexでこのZIPを導入し、競合はこのMODを後にしてください。\n'
       '描画NIFと革の色・法線、木とエンブレムの法線DDSだけを上書きします。\n'
       '22ノード、19節、75%の基準スケール、15衝突形状は維持しています。DLL・ESP・音声は本体のままです。\n'
       '柄の紐はメッシュを削除し、革の色とノーマルへ焼き込みました。紐だけの輪郭の出っ張りはありません。\n'
       + ('前回の外観テストMOD（47k版・3,980三角形版）は無効化してから今回のZIPを導入してください。\n'
          'エンブレムも曲面の土台だけを残し、浮き彫りをノーマルへ焼き込みました。\n'
          f"血用2形状込みのNIF総三角形: {report['nif_total_triangles']:,}（4,000以下）。輪郭は近距離で多角形に見える場合があります。\n"
          if report['format']=='cms-blender-under4k-v2' else '') +
       ('革の上下に木へ接する薄い縁を計48三角形追加し、中央の分割を32三角形整理しました。\n'
        '革の縁は前回の検証済み形状を維持しています。\n'
        if report.get('leather_edge_finish') else '') +
       ('鉄球の14本のスパイクは根元だけを内側に延ばし、底面全体を鉄球内部に接合しました。先端、UV、法線、面数、他の30表示メッシュ、テクスチャは維持。\n'
        if report.get('spike_contact_finish') else '') +
       f"三角形数: {report['before_triangles']:,} → {report['after_triangles']:,}（血・衝突形状を除く描画用）\n"
       '血用2形状は軽量化した鉄球に合わせて再生成し、ファイル構造と法線オフセットを確認しました。\n'
       'Skyrim VR実機、FPS、装備解除、掴み、接触、血の発生、xEditの確認は未実施です。正式完成版ではありません。\n'
       '戻し方: このテストMODだけをVortexで無効化または削除し、配置を更新してください。本体は有効のままにします。\n'
       '確認してほしい点: 手元の革と紐、木の傷、鉄球とエンブレムを複数の照明で確認。通常の掴み・振り・装備解除・血も確認。\n').encode('utf-8')
    files['SHA256SUMS_OPTIMIZED_TEST.txt']=''.join(sha256(v)+'  '+k+'\n' for k,v in sorted(files.items())).encode()
    with ZipFile(a.out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for name,value in sorted(files.items()):
            info_name=name
            z.writestr(info_name,value)
    print('OPTIMIZED_VISUAL_OVERLAY_PASS',a.out,report['after_triangles'],sha256(a.out.read_bytes()))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('cms','baseline-cms','blend','textures','writer','out'):p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--baseline-zip',type=Path)
    package(p.parse_args())
