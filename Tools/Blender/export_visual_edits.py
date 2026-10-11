"""Guarded Blender 4.5 -> CMS export for small audit6 surface/UV edits.

Preserves original lines for unchanged meshes, nodes and collision hulls.
Topology changes require a separate reviewed exporter/physics update.
"""
import argparse
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cms_io import parse, sha256, BASELINE_SHA256, AUDIT6_COMMIT, MATERIALS
import bpy
import numpy as np
from mathutils import Matrix


def require(ok, message):
    if not ok:
        raise ValueError(message)


def matrix_close(a, b, tolerance=2e-6):
    return all(abs(a[i][j]-b[i][j])<=tolerance for i in range(4) for j in range(4))


def derived_normals(positions, original, faces):
    normals = np.zeros_like(positions)
    triangles = positions[np.asarray(faces)]
    area = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    require(np.all(np.linalg.norm(area, axis=1)>1e-13), 'Edit creates a degenerate triangle')
    old_triangles = original[np.asarray(faces),:3]
    old_area = np.cross(old_triangles[:,1]-old_triangles[:,0],old_triangles[:,2]-old_triangles[:,0])
    require(np.all(np.sum(area*old_area,axis=1)>0), 'Edit folds or inverts a triangle')
    for corner in range(3):
        np.add.at(normals, np.asarray(faces)[:,corner], area)
    # Weld only coincident original seam vertices with matching authored normals.
    groups = {}
    for i, v in enumerate(original):
        key = tuple(np.round(v[:3],8))+tuple(np.round(v[3:6],3))
        groups.setdefault(key,[]).append(i)
    for indices in groups.values():
        if len(indices)>1:
            # A moved seam must stay coincident; otherwise it is a real split.
            if np.max(np.linalg.norm(positions[indices]-positions[indices[0]],axis=1)) < 1e-7:
                normals[indices] = normals[indices].sum(axis=0)
    lengths = np.linalg.norm(normals,axis=1)
    tiny = lengths<1e-12
    normals[tiny] = original[tiny,3:6]
    normals /= np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    return normals


def export(out):
    require(bpy.context.mode=='OBJECT', 'Switch to Object Mode before export')
    baseline = bpy.data.texts.get('AUDIT6_BASELINE.cms')
    require(baseline is not None, 'Missing embedded audit6 baseline')
    cms = parse(baseline.as_string().encode('utf-8'))
    require(bpy.context.scene.unit_settings.scale_length==1, 'Scene unit scale changed')
    bpy.context.view_layer.update()
    nodes = []
    for i,n in enumerate(cms['nodes']):
        obj = bpy.data.objects.get(n['name'])
        require(obj is not None and obj.type=='EMPTY', 'Missing runtime node '+n['name'])
        require(obj.get('cms_node_index')==i, 'Runtime node identity changed: '+n['name'])
        require(obj.parent==(nodes[n['parent']] if n['parent']>=0 else None), 'Runtime parent changed: '+n['name'])
        expected = Matrix([n['r'][j:j+3] for j in (0,3,6)]).to_4x4()
        expected.translation = n['t']
        require(matrix_close(obj.matrix_local,expected), 'Runtime transform changed: '+n['name'])
        require(not obj.constraints and not obj.animation_data, 'Animated/constrained runtime node: '+n['name'])
        nodes.append(obj)
    actual = [o for o in bpy.data.objects if 'cms_mesh_index' in o]
    require(len(actual)==len(cms['meshes']), 'Visual meshes were added/deleted/duplicated')
    collection = bpy.data.collections.get('02_Visuals_EDIT')
    require(collection is not None, 'Missing editable collection')
    require(set(collection.all_objects)==set(actual), 'Untracked object in the editable collection')
    chunks = [''.join(cms['lines'][:cms['meshes'][0]['start']])]
    changes = []
    all_world = []
    baseline_world = []
    for i,m in enumerate(cms['meshes']):
        obj = bpy.data.objects.get(m['name'])
        require(obj is not None and obj.get('cms_mesh_index')==i, 'Mesh identity changed: '+m['name'])
        require(obj.parent==nodes[m['parent']], 'Mesh parent changed: '+m['name'])
        require(matrix_close(obj.matrix_local,Matrix.Identity(4)), 'Apply no object transforms; edit vertices: '+m['name'])
        require(not obj.modifiers and not obj.constraints and not obj.animation_data and not obj.data.shape_keys,
                'Unapplied modifier/constraint/animation/shape key: '+m['name'])
        mesh=obj.data
        require(len(mesh.vertices)==len(m['vertices']), 'Vertex count changed: '+m['name'])
        require([tuple(p.vertices) for p in mesh.polygons]==m['faces'], 'Triangle indices/winding changed: '+m['name'])
        require(len(mesh.materials)==1 and mesh.materials[0] is not None and
                mesh.materials[0].name=='CMS_'+MATERIALS[m['material']] and
                mesh.materials[0].get('cms_material_index')==m['material'], 'Material assignment changed: '+m['name'])
        require(all(p.material_index==0 for p in mesh.polygons), 'Face material changed: '+m['name'])
        require(len(mesh.uv_layers)==1, 'Expected one CMS UV map: '+m['name'])
        original=np.asarray(m['vertices'],dtype=np.float64)
        values=original.copy()
        positions=np.asarray([v.co[:] for v in mesh.vertices],dtype=np.float64)
        require(np.isfinite(positions).all(), 'Non-finite vertex: '+m['name'])
        uv=np.full((len(mesh.vertices),2),np.nan)
        for loop, corner in zip(mesh.loops,mesh.uv_layers[0].data):
            v=loop.vertex_index; value=np.asarray(corner.uv[:])
            require(np.isfinite(value).all(), 'Non-finite UV: '+m['name'])
            if np.isfinite(uv[v]).all():
                require(np.max(np.abs(uv[v]-value))<1e-6, 'New UV seam needs vertex splitting: '+m['name'])
            uv[v]=value
        unused=~np.isfinite(uv).all(axis=1); uv[unused]=original[unused,6:8]
        moved=np.max(np.abs(positions-original[:,:3]))>1e-7
        uv_changed=np.max(np.abs(uv-original[:,6:8]))>1e-6
        maximum=float(np.max(np.linalg.norm(positions-original[:,:3],axis=1)))
        require(maximum<=.0020001, 'More than 2 mm deformation; review collision/runtime contract first: '+m['name'])
        # Blender stores float32. Ignore that import roundoff for a byte-identical no-edit export.
        if moved: values[:,:3]=positions; values[:,3:6]=derived_normals(positions,original,m['faces'])
        if uv_changed: values[:,6:8]=uv
        if moved or uv_changed:
            rows=[cms['lines'][m['start']]]
            rows += [' '.join(format(float(x),'.9g') for x in v)+'\n' for v in values]
            rows += cms['lines'][m['start']+1+len(values):m['end']]
            chunks.append(''.join(rows))
            changes.append(dict(mesh=m['name'],positions_changed=bool(moved),uv_changed=bool(uv_changed),
                                max_displacement_mm=maximum*1000))
        else:
            chunks.append(''.join(cms['lines'][m['start']:m['end']]))
        transform=np.asarray(obj.matrix_world,dtype=float)
        all_world.extend(values[:,:3]@transform[:3,:3].T+transform[:3,3])
        baseline_world.extend(original[:,:3]@transform[:3,:3].T+transform[:3,3])
    chunks.append(''.join(cms['lines'][cms['collision_start']:]))
    edited=np.asarray(all_world); original_world=np.asarray(baseline_world)
    bounds=[edited.min(axis=0).tolist(),edited.max(axis=0).tolist()]
    # Reusing audit6's ESP is only safe inside the established inventory bounds.
    require(np.all(edited.min(axis=0)>=original_world.min(axis=0)-1e-7) and
            np.all(edited.max(axis=0)<=original_world.max(axis=0)+1e-7),
            'Edit expands baseline bounds; update ESP bounds and the release pipeline first')
    data=''.join(chunks).encode('utf-8')
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
    blend=Path(bpy.data.filepath) if bpy.data.filepath else None
    report=dict(format='cms-blender-edit-v1',baseline_commit=AUDIT6_COMMIT,baseline_cms_sha256=BASELINE_SHA256,
                edited_cms_sha256=sha256(data),saved_blend_sha256=sha256(blend.read_bytes()) if blend and blend.is_file() else None,
                unsaved_blender_changes=bool(bpy.data.is_dirty),node_count=len(nodes),mesh_count=len(actual),
                collision_hulls=15,nodes_and_collision_bytes_preserved=True,
                topology_preserved=True,bounds_m=bounds,changes=changes,
                texture_exported=False,notes=['Textures/material shaders are not exported by this tool.',
                '2 mm is an editing guard, not a guarantee of game collision fidelity; test edited surfaces in VR.',
                'Normals are recomputed for deformed meshes; unchanged mesh records remain byte-identical.',
                'This report is not a formal runtime or release approval.'])
    out.with_suffix('.edit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('BLENDER_EXPORT_PASS',sha256(data),'changed meshes:',len(changes))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--blend',type=Path)
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    a=p.parse_args(args)
    if a.blend: bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    export(a.out)
