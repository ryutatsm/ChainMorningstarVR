"""Integration checks in Blender 4.5/bpy; no Skyrim runtime claims.

blender --background --python Tests/test_blender_handoff.py -- --blend PATH --out DIR
"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Tools/Blender'))
import bpy
from cms_io import BASELINE_SHA256, sha256
from export_visual_edits import export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    a=parser.parse_args(args); a.out.mkdir(parents=True,exist_ok=True)
    def reset():
        bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    def rejected(name, change, expected):
        reset(); change()
        try: export(a.out/(name+'.cms'))
        except ValueError as e:
            assert expected in str(e),(name,str(e)); print('REJECTION_PASS',name)
        else: raise AssertionError('Accepted unsafe edit: '+name)
    reset()
    assert len([i for i in bpy.data.images if i.packed_file])==21
    baseline=a.out/'unchanged.cms'; result=export(baseline)
    assert sha256(baseline.read_bytes())==BASELINE_SHA256 and result['changes']==[]
    wood='CMS_CMS_ROOT_wood'; head='CMS_CMS_HeadNode_metal'
    for name in (wood,head):
        reset(); mesh=bpy.data.objects[name].data
        mesh.vertices[300].co *= .9995; mesh.update()
        result=export(a.out/('edited_'+name+'.cms'))
        assert len(result['changes'])==1 and result['changes'][0]['positions_changed']
    rejected('runtime_translation',lambda:setattr(bpy.data.objects['CMS_ChainAnchor'].location,'y',.31),'Runtime transform')
    rejected('object_scale',lambda:setattr(bpy.data.objects[wood],'scale',(1.1,1,1)),'object transforms')
    rejected('wrong_parent',lambda:setattr(bpy.data.objects[wood],'parent',None),'parent')
    rejected('modifier',lambda:bpy.data.objects[wood].modifiers.new('Subdivision','SUBSURF'),'Unapplied modifier')
    rejected('material',lambda:bpy.data.objects[wood].data.materials.clear(),'Material assignment')
    rejected('deformation',lambda:setattr(bpy.data.objects[wood].data.vertices[300].co,'x',.1),'2 mm')
    def extra_mesh():
        obj=bpy.data.objects[wood].copy(); obj.data=obj.data.copy()
        bpy.data.collections['02_Visuals_EDIT'].objects.link(obj)
    rejected('duplicate',extra_mesh,'added/deleted/duplicated')
    def seam():
        uv=bpy.data.objects[wood].data.uv_layers[0]
        uv.data[1].uv.x += .1
    rejected('uv_seam',seam,'New UV seam')
    def topology():
        mesh=bpy.data.objects[wood].data; mesh.clear_geometry()
    rejected('topology',topology,'Vertex count')
    reset()
    print('BLENDER_HANDOFF_TESTS_PASS: exact no-edit roundtrip, 2 surface edits, 9 rejected invalid edits, 21 packed images')


if __name__=='__main__': main()
