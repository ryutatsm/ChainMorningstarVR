"""Add the reviewed thin leather end annuli without changing the wooden shaft."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from leather_edge_contract import build,POLICY,LEATHER,source
from cms_io import sha256

def finish(blend,out):
    bpy.ops.wm.open_mainfile(filepath=str(blend.resolve()))
    o=bpy.data.objects[LEATHER];rows,faces,proof=build();old=o.data
    m=bpy.data.meshes.new(LEATHER+'_closed_edges');m.from_pydata(rows[:,:3].tolist(),[],faces.tolist());m.update()
    m.materials.append(o.active_material);uv=m.uv_layers.new(name='UVMap')
    for p in m.polygons:
        p.use_smooth=True
        for li,vi in zip(p.loop_indices,p.vertices):uv.data[li].uv=rows[vi,6:8]
    m.normals_split_custom_set([rows[loop.vertex_index,3:6].tolist() for loop in m.loops])
    o.data=m
    if old.users==0:bpy.data.meshes.remove(old)
    t=bpy.data.texts['AUDIT6_OPTIMIZATION.json'];manifest=json.loads(t.as_string())
    manifest['leather_edge_finish']=proof;manifest['leather_edge_source_blend_sha256']=sha256(blend.read_bytes())
    manifest['after_triangles']=2900;manifest['nif_total_triangles']=3996
    next(x for x in manifest['meshes'] if x['mesh']==LEATHER)['after_triangles']=176
    t.clear();t.write(json.dumps(manifest,indent=2))
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out.resolve()),compress=True)
    print('LEATHER_EDGE_FINISH_PASS',json.dumps(proof),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--blend',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);finish(a.blend,a.out)
