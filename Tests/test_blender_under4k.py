"""Blender integration gate for the explicit inclusive 4k retopology route."""
import argparse,json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Tools/Blender'))
from export_under4k_visuals import export
from export_optimized_visuals import export as strict_export
from cms_io import load,sha256

def main(a):
    a.out=a.out.resolve();a.textures=a.textures.resolve();a.out.mkdir(parents=True,exist_ok=True)
    def open_scene():bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    open_scene();r=export(a.out/'first.cms',a.textures,True);c=load(a.out/'first.cms',False)
    assert r['nif_total_triangles']<=4000 and r['after_triangles']<=4000
    assert r['node_count']==22 and r['chain_links']==19 and r['collision_hulls']==15 and r['mesh_count']==31
    assert len(next(m for m in c['meshes'] if m['name'].endswith('_emblem'))['faces'])==100
    rejections=[]
    def reject(name,mutate,expected,old=False):
        open_scene();mutate()
        try:(strict_export if old else export)(a.out/'unsafe.cms',a.textures)
        except ValueError as e:
            assert expected in str(e),(name,str(e));rejections.append(dict(test=name,reason=str(e)))
        else:raise AssertionError('Unsafe input accepted: '+name)
    def unit():bpy.context.scene.unit_settings.scale_length=.75
    def node():bpy.data.objects['CMS_LinkNode_00'].location.x+=.001
    def parent():bpy.data.objects['CMS_LinkNode_00'].parent=bpy.data.objects['CMS_ROOT']
    def hull():bpy.data.objects['CollisionHull_00'].data.vertices[0].co.x+=.001
    def deleted():bpy.data.objects.remove(bpy.data.objects['CMS_CMS_ROOT_edge'],do_unlink=True)
    def modifier():bpy.data.objects['CMS_CMS_ROOT_wood'].modifiers.new('Unsafe','SUBSURF')
    def large():
        for v in bpy.data.objects['CMS_CMS_ROOT_wood'].data.vertices:v.co.x+=.02
    def uv():
        for v in bpy.data.objects['CMS_CMS_ROOT_wood'].data.uv_layers[0].data:v.uv.x=1-v.uv.x
    def material():bpy.data.materials['CMS_wood']['cms_material_index']=0
    def budget():
        t=bpy.data.texts['AUDIT6_OPTIMIZATION.json'];m=json.loads(t.as_string());m['triangle_budget_including_blood']=5000
        t.clear();t.write(json.dumps(m))
    def texture():bpy.data.images['cms_emblem_n.png'].name='Missing_normal'
    for args in [('unit',unit,'Unit scale'),('node',node,'Runtime transform'),('parent',parent,'Runtime parent'),
        ('collision',hull,'Collision reference was edited'),('deletion',deleted,'Unexpected visual'),
        ('modifier',modifier,'Unapplied modifier'),('large edit',large,'bounds expanded'),
        ('UV mirror',uv,'UV winding'),('material',material,'Material contract'),('budget',budget,'budget/policy'),
        ('missing packed normal',texture,'Missing packed texture')]:reject(*args)
    reject('previous strict route remains strict',lambda:None,'Wrong optimization project',True)
    if r.get('leather_edge_finish'):
        def edge_gap():
            o=bpy.data.objects['CMS_CMS_ROOT_leather']
            o.data.vertices[102].co.x+=.001
        def edge_uv():
            o=bpy.data.objects['CMS_CMS_ROOT_leather']
            o.data.uv_layers[0].data[128*3].uv.x+=.01
        def unrelated():
            bpy.data.objects['CMS_CMS_ROOT_wood'].data.vertices[20].co.x+=.000001
        def policy():
            t=bpy.data.texts['AUDIT6_OPTIMIZATION.json'];m=json.loads(t.as_string())
            m['leather_edge_finish']['wood_inset_mm']=0
            t.clear();t.write(json.dumps(m))
        for args in [('detached leather edge',edge_gap,'Leather edge differs'),
                     ('edge UV change',edge_uv,'Leather edge differs'),
                     ('unrelated micron edit',unrelated,'Unrelated mesh changed'),
                     ('edge contact policy',policy,'independent contact proof')]:reject(*args)
        # Exercise the independent packaging/CI check without Blender geometry.
        from leather_edge_contract import validate_cms
        import copy
        unsafe=copy.deepcopy(c);m=next(m for m in unsafe['meshes'] if m['name']=='CMS_CMS_ROOT_leather')
        m['vertices'][m['faces'][128][0]][0]+=.001
        try:validate_cms(unsafe)
        except ValueError:rejections.append(dict(test='independent CI geometry check',reason='altered contact corner rejected'))
        else:raise AssertionError('CI accepted altered end annulus')
    open_scene();export(a.out/'second.cms',a.textures,True)
    assert (a.out/'first.cms').read_bytes()==(a.out/'second.cms').read_bytes()
    result=dict(draw_triangles=r['after_triangles'],blood_triangles=r['blood_triangles'],nif_total_triangles=r['nif_total_triangles'],
        deterministic_export=True,unsafe_cases_rejected=rejections,cms_sha256=sha256(c['data']))
    (a.out/'test_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('UNDER4K_TEST_PASS',len(rejections),'unsafe inputs rejected',r['nif_total_triangles'],'total triangles')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('blend','textures','out'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
