"""Integration gate for topology optimization: validate output and unsafe edits.

blender -b --python Tests/test_blender_optimization.py -- --blend PATH --textures DIR --out DIR
"""
import argparse
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Tools/Blender'))
from cms_io import load,sha256
from export_optimized_visuals import export
from export_visual_edits import export as small_edit_export


def main(a):
    a.out.mkdir(parents=True,exist_ok=True);rejections=[]
    def open_scene():bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    def rejected(name,mutation,expected,exporter=None):
        open_scene();mutation()
        try:
            if exporter:exporter(a.out/'unsafe.cms')
            else:export(a.out/'unsafe.cms',a.textures)
        except ValueError as error:
            if expected not in str(error):raise AssertionError(name+': unexpected error '+str(error)) from error
            rejections.append(dict(test=name,reason=str(error)))
        else:raise AssertionError('Unsafe edit accepted: '+name)
    open_scene();report=export(a.out/'roundtrip.cms',a.textures)
    cms=load(a.out/'roundtrip.cms',require_baseline=False)
    assert report['node_count']==22 and report['chain_links']==19 and report['collision_hulls']==15 and report['mesh_count']==31
    assert sum(len(m['vertices']) for m in cms['meshes'])<59859,'Corner splitting defeats vertex reduction'
    assert report['after_triangles']<report['before_triangles']*.5
    def unit():bpy.context.scene.unit_settings.scale_length=.75
    def node():bpy.data.objects['CMS_LinkNode_00'].location.x+=.001
    def parent():bpy.data.objects['CMS_LinkNode_00'].parent=bpy.data.objects['CMS_ROOT']
    def collision():bpy.data.objects['CollisionHull_00'].data.vertices[0].co.x+=.001
    def deleted():bpy.data.objects.remove(bpy.data.objects['CMS_CMS_ROOT_edge'],do_unlink=True)
    def modifier():bpy.data.objects['CMS_CMS_ROOT_wood'].modifiers.new('Unsafe','SUBSURF')
    def geometry():
        for v in bpy.data.objects['CMS_CMS_ROOT_wood'].data.vertices:v.co*=.99
    def uv():
        for c in bpy.data.objects['CMS_CMS_ROOT_wood'].data.uv_layers[0].data:c.uv.x=1-c.uv.x
    def material():bpy.data.materials['CMS_wood']['cms_material_index']=0
    def extra():
        mesh=bpy.data.meshes.new('Untracked');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
        obj=bpy.data.objects.new('Untracked',mesh);bpy.context.scene.collection.objects.link(obj)
    for args in [('unit',unit,'Unit scale'),('node-transform',node,'Runtime transform'),
                 ('node-parent',parent,'Runtime parent'),('collision',collision,'Collision reference was edited'),
                 ('unauthorized-deletion',deleted,'Unexpected visual addition/deletion'),
                 ('modifier',modifier,'Unapplied modifier'),('geometry',geometry,'Surface deviation'),
                 ('mirrored-uv',uv,'UV winding'),('material',material,'Material contract'),
                 ('untracked-mesh',extra,'Untracked scene mesh')]:rejected(*args)
    rejected('old-exporter-stays-strict',lambda:None,'Visual meshes were added/deleted/duplicated',small_edit_export)
    open_scene();second=export(a.out/'second.cms',a.textures)
    assert (a.out/'second.cms').read_bytes()==(a.out/'roundtrip.cms').read_bytes()
    result=dict(valid_export_sha256=sha256(cms['data']),before_triangles=report['before_triangles'],
                after_triangles=report['after_triangles'],vertices=sum(len(m['vertices']) for m in cms['meshes']),
                unsafe_cases_rejected=rejections,deterministic_export=True)
    (a.out/'test_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('BLENDER_OPTIMIZATION_TEST_PASS',len(rejections),'unsafe cases rejected',result['vertices'],'vertices')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('blend','textures','out'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);main(a)
