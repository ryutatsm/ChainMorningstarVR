"""Guarded topology-changing export for the explicit audit6 cord-bake project.

Do not use this as a general replacement for export_visual_edits.py. Only the
named cord may be removed; every other surface must pass the measured 0.15 mm
distance, orientation, component, UV, node, bounds and collision contracts.
"""
import argparse
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cms_io import parse,sha256,BASELINE_SHA256,AUDIT6_COMMIT,MATERIALS
from export_visual_edits import require,matrix_close
from surface_contract import SURFACE_LIMIT_M,REMOVED_MESH,distance_report,maximum,topology,orientation,uv_orientation


def serialize_mesh(obj):
    mesh=obj.data;mesh.calc_loop_triangles();mesh.update()
    require(len(mesh.uv_layers)==1,'Expected one UV map: '+obj.name)
    rows=[];faces=[];indices={}
    for triangle in mesh.loop_triangles:
        face=[]
        for loop_index in triangle.loops:
            loop=mesh.loops[loop_index]
            position=mesh.vertices[loop.vertex_index].co[:]
            normal=mesh.corner_normals[loop_index].vector[:]
            uv=mesh.uv_layers[0].data[loop_index].uv[:]
            values=tuple(position)+tuple(normal)+tuple(uv)
            require(np.isfinite(values).all(),'Non-finite export corner: '+obj.name)
            require(abs(np.linalg.norm(normal)-1)<1e-4,'Invalid normal: '+obj.name)
            # Split at actual UV/normal seams; NIF has one UV and normal per vertex.
            key=tuple(format(float(v),'.9g') for v in values)
            if key not in indices:indices[key]=len(rows);rows.append(values)
            face.append(indices[key])
        faces.append(face)
    require(0<len(rows)<65536 and 0<len(faces)<65536,'NIF index limit: '+obj.name)
    return np.array(rows),np.array(faces,dtype=int)


def export(out,textures,loaded_from_saved_file=False):
    dirty_on_entry=bool(bpy.data.is_dirty)
    require(bpy.context.mode=='OBJECT','Switch to Object Mode')
    require(bpy.context.scene.get('cms_optimization')=='audit6-cord-bake-v1','Wrong optimization project')
    require(bpy.context.scene.unit_settings.scale_length==1,'Unit scale changed')
    baseline=bpy.data.texts.get('AUDIT6_BASELINE.cms')
    require(baseline is not None,'Missing baseline')
    cms=parse(baseline.as_string().encode())
    text=bpy.data.texts.get('AUDIT6_OPTIMIZATION.json')
    require(text is not None,'Missing explicit optimization provenance')
    manifest=json.loads(text.as_string())
    require(manifest['baseline_cms_sha256']==BASELINE_SHA256 and
            manifest['baseline_commit']==AUDIT6_COMMIT and
            manifest['removed_mesh']==REMOVED_MESH,'Wrong baseline or deletion policy')
    require(manifest['surface_limit_mm']==SURFACE_LIMIT_M*1000,'Surface tolerance changed')
    require({t['name'] for t in manifest['texture_bakes']}==
            {'cms_leather_d.png','cms_leather_n.png','cms_wood_n.png','cms_emblem_n.png'},'Unexpected baked texture set')
    for texture in manifest['texture_bakes']:
        path=textures/texture['name']
        require(path.is_file() and sha256(path.read_bytes())==texture['sha256'],'Texture/provenance mismatch: '+path.name)
        image=bpy.data.images.get(texture['name'])
        require(image is not None and image.packed_file is not None and list(image.size)==[1024,1024],
                'Missing packed texture: '+path.name)
        require(sha256(bytes(image.packed_file.data))==texture['sha256'],'Packed texture differs from exported PNG: '+path.name)
    bpy.context.view_layer.update();nodes=[]
    for i,n in enumerate(cms['nodes']):
        obj=bpy.data.objects.get(n['name'])
        require(obj is not None and obj.type=='EMPTY' and obj.get('cms_node_index')==i,'Runtime node changed: '+n['name'])
        require(obj.parent==(nodes[n['parent']] if n['parent']>=0 else None),'Runtime parent changed: '+n['name'])
        expected=Matrix([n['r'][j:j+3] for j in (0,3,6)]).to_4x4();expected.translation=n['t']
        require(matrix_close(obj.matrix_local,expected),'Runtime transform changed: '+n['name'])
        require(not obj.constraints and not obj.animation_data,'Animated runtime node: '+n['name'])
        nodes.append(obj)
    require(len(nodes)==22 and sum(n['name'].startswith('CMS_LinkNode_') for n in cms['nodes'])==19,'Wrong runtime hierarchy')
    runtime_collection=bpy.data.collections.get('01_Runtime_nodes_KEEP')
    require(runtime_collection is not None and set(runtime_collection.all_objects)==set(nodes),'Untracked runtime node')
    collisions=bpy.data.collections.get('03_Collision_reference_KEEP')
    require(collisions is not None and len(collisions.all_objects)==15,'Collision reference count changed')
    for i,hull in enumerate(cms['hulls']):
        obj=bpy.data.objects.get(f'CollisionHull_{i:02d}')
        require(obj is not None and obj.name in collisions.all_objects and obj.parent==nodes[-1] and
                matrix_close(obj.matrix_local,Matrix.Identity(4)),'Collision reference identity changed')
        positions=np.array(sorted(tuple(v.co[:]) for v in obj.data.vertices))
        expected=np.array(sorted(tuple(v) for v in hull['vertices']))
        require(positions.shape==expected.shape and np.allclose(positions,expected,atol=1e-7,rtol=0),
                'Collision reference was edited: '+obj.name)
    originals=[m for m in cms['meshes'] if m['name']!=REMOVED_MESH]
    expected_names={m['name'] for m in originals}
    actual=[o for o in bpy.data.objects if 'cms_mesh_index' in o]
    require({o.name for o in actual}==expected_names and len(actual)==31,'Unexpected visual addition/deletion')
    collection=bpy.data.collections.get('02_Visuals_EDIT')
    require(collection is not None and set(collection.all_objects)==set(actual),'Untracked editable object')
    require({o for o in bpy.data.objects if o.type=='MESH'}==set(actual)|set(collisions.all_objects),'Untracked scene mesh')
    require(bpy.data.objects.get(REMOVED_MESH) is None,'Cord geometry was not removed')
    first=cms['meshes'][0]['start'];prefix=list(cms['lines'][:first])
    prefix[1]=f"{len(nodes)} {len(originals)} {len(cms['hulls'])}\n"
    chunks=[''.join(prefix)];reports=[];world=[];original_world=[]
    for original in cms['meshes']:
        parent=nodes[original['parent']];transform=np.array(parent.matrix_world)
        old=np.array(original['vertices']);p=old[:,:3];f=np.array(original['faces'])
        original_world.extend(p@transform[:3,:3].T+transform[:3,3])
        if original['name']==REMOVED_MESH:continue
        obj=bpy.data.objects[original['name']]
        require(obj.get('cms_mesh_index')==cms['meshes'].index(original),'Mesh identity changed: '+obj.name)
        require(obj.parent==parent and matrix_close(obj.matrix_local,Matrix.Identity(4)),'Mesh transform/parent changed: '+obj.name)
        require(not obj.modifiers and not obj.constraints and not obj.animation_data and not obj.data.shape_keys,
                'Unapplied modifier/animation: '+obj.name)
        require(len(obj.data.materials)==1 and obj.active_material.name=='CMS_'+MATERIALS[original['material']] and
                obj.active_material.get('cms_material_index')==original['material'] and
                all(p.material_index==0 for p in obj.data.polygons),'Material contract changed: '+obj.name)
        rows,g=serialize_mesh(obj);q=rows[:,:3]
        require(len(g)<=len(f),'Optimization increases triangles: '+obj.name)
        uv=rows[:,6:8];old_uv=old[:,6:8]
        require(np.all(uv.min(0)>=old_uv.min(0)-1e-5) and np.all(uv.max(0)<=old_uv.max(0)+1e-5),
                'UV escaped its authored domain: '+obj.name)
        require(np.all(q.min(0)>=p.min(0)-1e-7) and np.all(q.max(0)<=p.max(0)+1e-7),
                'Authored bounds expanded: '+obj.name)
        distances=distance_report(p,f,q,g)
        require(maximum(distances)<=SURFACE_LIMIT_M+1e-8,'Surface deviation exceeds 0.15 mm: '+obj.name)
        old_topology=topology(p,f);new_topology=topology(q,g)
        require(old_topology==new_topology,'Connected surfaces/holes changed: '+obj.name)
        minimum_dot=orientation(p,f,q,g)
        try:checked_uv=uv_orientation(p,f,old[:,6:8],q,g,uv)
        except ValueError as error:raise ValueError(obj.name+': '+str(error)) from error
        chunks.append(f"{obj.name} {original['parent']} {original['material']} {len(rows)} {len(g)}\n")
        chunks.extend(' '.join(format(float(v),'.9g') for v in row)+'\n' for row in rows)
        chunks.extend(' '.join(map(str,tri))+'\n' for tri in g)
        world.extend(q@transform[:3,:3].T+transform[:3,3])
        reports.append(dict(mesh=obj.name,before_triangles=len(f),after_triangles=len(g),
                            distances=distances,surface_topology=old_topology,
                            minimum_face_normal_dot=minimum_dot,uv_domain_preserved=True))
        reports[-1].update(uv_orientation_verified=True,uv_triangles_checked=checked_uv)
    collision_bytes=''.join(cms['lines'][cms['collision_start']:]);chunks.append(collision_bytes)
    data=''.join(chunks).encode();edited=parse(data,require_baseline=False)
    require(edited['nodes']==cms['nodes'] and edited['hulls']==cms['hulls'],'Node/collision serialization changed')
    require(''.join(edited['lines'][edited['collision_start']:])==collision_bytes,'Collision bytes changed')
    before=np.array(original_world);after=np.array(world)
    require(np.all(after.min(0)>=before.min(0)-1e-7) and np.all(after.max(0)<=before.max(0)+1e-7),'Inventory bounds expanded')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    report=dict(format='cms-blender-optimized-v1',baseline_commit=AUDIT6_COMMIT,
                baseline_cms_sha256=BASELINE_SHA256,edited_cms_sha256=sha256(data),
                saved_blend_sha256=sha256(Path(bpy.data.filepath).read_bytes()),
                unsaved_blender_changes=dirty_on_entry,removed_mesh=REMOVED_MESH,
                source_loaded_from_saved_file=loaded_from_saved_file,
                before_triangles=sum(len(m['faces']) for m in cms['meshes']),
                after_triangles=sum(len(m['faces']) for m in edited['meshes']),
                surface_limit_mm=SURFACE_LIMIT_M*1000,meshes=reports,
                node_count=22,chain_links=19,mesh_count=31,collision_hulls=15,
                nodes_and_collision_bytes_preserved=True,topology_preserved=False,
                before_bounds_m=[before.min(0).tolist(),before.max(0).tolist()],
                bounds_m=[after.min(0).tolist(),after.max(0).tolist()],
                texture_bakes=manifest['texture_bakes'],texture_exported=True,
                source_blend_sha256=manifest['source_blend_sha256'],runtime_tested=False,xedit_tested=False,
                notes=['Dense bidirectional sampled surface distances, not an exact Hausdorff guarantee.',
                       'The intentionally removed cord has texture shading and no silhouette displacement.',
                       'Blood surfaces must be regenerated from optimized head geometry by the pinned NIF writer.',
                       'A successful export does not confirm Skyrim VR behavior or formal release readiness.'])
    out.with_suffix('.edit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('OPTIMIZED_EXPORT_PASS',report['before_triangles'],report['after_triangles'],sha256(data),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blend',type=Path,required=True);p.add_argument('--textures',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()));export(a.out,a.textures,loaded_from_saved_file=True)
