"""Explicit cord-to-leather bake and bounded audit6 mesh simplification.

Run with Blender 4.5 background. Read the original authored blend, not a generated
replacement. All runtime objects and collision references are retained unchanged.
"""
import argparse
import json
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cms_io import parse,sha256,BASELINE_SHA256,AUDIT6_COMMIT
from surface_contract import (SURFACE_LIMIT_M,REMOVED_MESH,NORMAL_BAKES,
                              surface,distance_report,maximum,topology,orientation,uv_orientation,barycentric)
DEBUG_DIR=None


def geometry(obj):
    mesh=obj.data;mesh.calc_loop_triangles()
    return (np.array([v.co[:] for v in mesh.vertices]),
            np.array([t.vertices[:] for t in mesh.loop_triangles],dtype=int))


def select(objects,active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=active


def candidate(high,ratio,original):
    obj=high.copy();obj.data=high.data.copy()
    bpy.data.collections['02_Visuals_EDIT'].objects.link(obj)
    obj.data.name=high.data.name+'_LOW'
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    select([obj],obj)
    mod=obj.modifiers.new('BoundedReduction','DECIMATE')
    mod.ratio=ratio;mod.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # Quadric collapse can overshoot slightly. Never enlarge authored dimensions.
    lower=original.min(0);upper=original.max(0)
    for v in obj.data.vertices:v.co=np.clip(v.co[:],lower,upper)
    # Collapse interpolation can extrapolate corner UVs slightly beyond an edge.
    # Keep the original texture domain before baking and serializing the result.
    source_uv=np.array([corner.uv[:] for corner in high.data.uv_layers[0].data])
    uv_lower=source_uv.min(0);uv_upper=source_uv.max(0)
    for corner in obj.data.uv_layers[0].data:
        corner.uv=np.clip(corner.uv[:],uv_lower,uv_upper)
    obj.data.update()
    return obj


def destroy(obj):
    mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
    if mesh.users==0:bpy.data.meshes.remove(mesh)


def transfer_normals(obj,original):
    p=np.array(original['vertices'])[:,:3];f=np.array(original['faces'])
    n=np.array(original['vertices'])[:,3:6];tree=surface(p,f)
    mesh=obj.data;result=[None]*len(mesh.loops)
    canonical={}
    for vertex in mesh.vertices:
        near,_,tri,_=tree.find_nearest(vertex.co);indices=f[tri]
        weights=barycentric(np.array(near),*p[indices]);normal=weights@n[indices]
        normal/=max(np.linalg.norm(normal),1e-12);canonical[vertex.index]=normal
    for poly in mesh.polygons:
        center=np.mean([mesh.vertices[i].co[:] for i in poly.vertices],axis=0)
        for index in poly.loop_indices:
            vertex=mesh.vertices[mesh.loops[index].vertex_index]
            # Query just inside this face to select the right side of hard seams.
            query=np.asarray(vertex.co[:])*.9999+center*.0001
            near,_,tri,_=tree.find_nearest(Vector(query));indices=f[tri]
            weights=barycentric(np.array(near),*p[indices]);normal=weights@n[indices]
            normal/=max(np.linalg.norm(normal),1e-12)
            # Give a smooth shared vertex ONE normal; avoid per-corner subpixel
            # differences splitting every exported triangle into three vertices.
            # Retain a distinct normal at genuine hard cap/plate boundaries.
            default=canonical[vertex.index]
            if np.dot(default,normal)>.9999:normal=default
            result[index]=normal.tolist()
        poly.use_smooth=True
    mesh.normals_split_custom_set(result);mesh.update()


def reduce(high,original):
    p=np.array(original['vertices'])[:,:3];f=np.array(original['faces'])
    expected=topology(p,f);lo=.03;hi=1.;best=None;trials=[]
    # Only select a candidate that was actually measured and passed all checks.
    for iteration in range(8):
        ratio=(lo+hi)*.5;obj=candidate(high,ratio,p);q,g=geometry(obj)
        distances=distance_report(p,f,q,g)
        reason=None
        try:
            if maximum(distances)>SURFACE_LIMIT_M:raise ValueError('surface error')
            if topology(q,g)!=expected:raise ValueError('surface topology')
            orientation(p,f,q,g)
            corner_positions=np.array([obj.data.vertices[loop.vertex_index].co[:] for loop in obj.data.loops])
            corner_uv=np.array([corner.uv[:] for corner in obj.data.uv_layers[0].data])
            corner_faces=np.array([t.loops[:] for t in obj.data.loop_triangles])
            uv_orientation(p,f,np.array(original['vertices'])[:,6:8],corner_positions,corner_faces,corner_uv)
        except ValueError as error:reason=str(error)
        trials.append(dict(ratio=ratio,triangles=len(g),max_mm=maximum(distances)*1000,rejection=reason))
        if reason:
            lo=ratio;destroy(obj)
        else:
            hi=ratio
            if best:destroy(best)
            best=obj
    if best is None:raise ValueError('No shape-preserving reduction for '+original['name'])
    transfer_normals(best,original)
    q,g=geometry(best)
    report=dict(mesh=original['name'],before_triangles=len(f),after_triangles=len(g),
                collapse_ratio=hi,distances=distance_report(p,f,q,g),
                surface_topology=expected,trials=trials)
    print('REDUCED',json.dumps(report),flush=True)
    return best,report


def pixel_array(image):
    values=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(values)
    return values.reshape(image.size[1],image.size[0],4)


def bake(low,sources,kind,name,cage_extrusion=.0045,max_ray_distance=.009):
    image=bpy.data.images.new('BAKE_'+name,width=1024,height=1024,alpha=True)
    image.alpha_mode='CHANNEL_PACKED'
    image.colorspace_settings.name='sRGB' if kind=='DIFFUSE' else 'Non-Color'
    target=low.active_material.node_tree.nodes.new('ShaderNodeTexImage');target.image=image
    low.active_material.node_tree.nodes.active=target
    for node in low.active_material.node_tree.nodes:node.select=node==target
    select(sources+[low],low)
    scene=bpy.context.scene
    scene.render.bake.use_selected_to_active=True
    cage=None
    if 'leather' in name:
        cage=low.copy();cage.data=low.data.copy();cage.name='TEMP_LEATHER_CAGE'
        bpy.context.collection.objects.link(cage)
        cage.select_set(False);cage.hide_render=True
        for v in cage.data.vertices:
            direction=Vector((v.co.x,0,v.co.z));direction.normalize();v.co+=direction*cage_extrusion
        scene.render.bake.use_cage=True;scene.render.bake.cage_object=cage
    else:scene.render.bake.use_cage=False
    scene.render.bake.cage_extrusion=cage_extrusion
    scene.render.bake.max_ray_distance=max_ray_distance
    scene.render.bake.margin=12
    scene.render.bake.use_clear=True
    scene.render.bake.normal_space='TANGENT'
    scene.render.bake.normal_r='POS_X';scene.render.bake.normal_g='POS_Y';scene.render.bake.normal_b='POS_Z'
    scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True
    print('BAKE_START',name,kind,flush=True)
    bpy.ops.object.bake(type=kind)
    if DEBUG_DIR:
        image.filepath_raw=str(DEBUG_DIR/(name+'.png'));image.file_format='PNG';image.save()
    if cage:
        scene.render.bake.cage_object=None;scene.render.bake.use_cage=False;destroy(cage)
    low.active_material.node_tree.nodes.remove(target)
    print('BAKE_DONE',name,kind,flush=True)
    return image


def bake_alpha(low,sources,coverage=None,**bake_options):
    original=[obj.active_material for obj in sources];temporary=[]
    for obj,old in zip(sources,original):
        mat=old.copy();obj.data.materials[0]=mat;temporary.append(mat)
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        normal=next(n for n in nodes if n.type=='TEX_IMAGE' and n.image and n.image.name.endswith('_n.png'))
        output=nodes.get('Material Output');emission=nodes.new('ShaderNodeEmission')
        links.new(normal.outputs['Alpha'],emission.inputs['Color'])
        links.new(emission.outputs[0],output.inputs['Surface'])
    image=bake(low,sources,'EMIT','leather_specular',**bake_options)
    values=pixel_array(image);alpha=values[:,:,0].copy()
    print('SPECULAR_BAKE_STATS',float(alpha.min()),float(alpha.max()),float(np.mean(values[:,:,3]<.5)),flush=True)
    missing=(values[:,:,3]<.5)|(values[:,:,0]<.01)
    checked=missing if coverage is None else missing[coverage]
    if np.mean(checked)>.005:raise ValueError('Too many missing specular bake pixels')
    fallback=pixel_array(bpy.data.images['cms_leather_n.png'])[:,:,3]
    alpha[missing]=fallback[missing]
    bpy.data.images.remove(image)
    for obj,old in zip(sources,original):obj.data.materials[0]=old
    for mat in temporary:bpy.data.materials.remove(mat)
    if alpha.min()<.01 or alpha.max()>.7:raise ValueError('Specular bake has empty or excessive pixels')
    return alpha


def install_image(image,name,output,alpha,coverage=None):
    old=bpy.data.images[name];values=pixel_array(image)
    missing=values[:,:,3]<.5
    checked=missing if coverage is None else missing[coverage]
    if 'leather' in name and np.mean(checked)>.005:raise ValueError('Too many unmapped leather pixels')
    # Outside a UV island, or at a subpixel projection miss, retain source pixels.
    # Alpha is specular, so do this before replacing the bake coverage channel.
    values[missing,:3]=pixel_array(old)[missing,:3]
    values[:,:,3]=alpha
    if not np.isfinite(values).all():raise ValueError('Non-finite bake')
    if name.endswith('_n.png'):
        normals=values[:,:,:3]*2-1;length=np.linalg.norm(normals,axis=2)
        if length.min()<.5:raise ValueError('Incomplete normal bake '+name)
        normals/=length[:,:,None];values[:,:,:3]=normals*.5+.5
    image.pixels.foreach_set(values.ravel());image.update()
    image.filepath_raw=str(output/name);image.file_format='PNG';image.save()
    old.user_remap(image);bpy.data.images.remove(old)
    image.name=name;image.pack();image.filepath='//textures/'+name
    return dict(name=name,sha256=sha256((output/name).read_bytes()),
                size=[1024,1024],source_fallback_pixels=int(missing.sum()),
                alpha_min=float(values[:,:,3].min()),alpha_max=float(values[:,:,3].max()))


def optimize(a):
    global DEBUG_DIR
    a.blend=a.blend.resolve();a.out=a.out.resolve();a.textures=a.textures.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    cms=parse(bpy.data.texts['AUDIT6_BASELINE.cms'].as_string().encode())
    if bpy.context.scene.get('cms_baseline_sha256')!=BASELINE_SHA256:raise ValueError('Wrong blend baseline')
    if bpy.context.scene.unit_settings.scale_length!=1:raise ValueError('Wrong unit scale')
    a.textures.mkdir(parents=True,exist_ok=True);a.out.parent.mkdir(parents=True,exist_ok=True)
    DEBUG_DIR=a.textures/'debug';DEBUG_DIR.mkdir(exist_ok=True)
    high_collection=bpy.data.collections.new('TEMP_BAKE_SOURCE');bpy.context.scene.collection.children.link(high_collection)
    highs={};lows={};reports=[];textures=[];cache={}
    for original in cms['meshes']:
        name=original['name'];high=bpy.data.objects[name]
        if name==REMOVED_MESH:
            highs[name]=high;continue
        key=sha256(np.asarray(original['vertices']).tobytes()+np.asarray(original['faces']).tobytes())
        if key in cache:
            template,cached=cache[key];low=high.copy();low.data=template.data.copy()
            bpy.data.collections['02_Visuals_EDIT'].objects.link(low)
            report=dict(cached);report['mesh']=name
        else:
            low,report=reduce(high,original);cache[key]=(low,report)
        low.data.materials[0]=high.active_material.copy()
        highs[name]=high;lows[name]=low;reports.append(report)
    # Source geometry remains unchanged until all bakes finish.
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out.with_name('optimization_bake_sources.blend')),copy=True)
    for base in NORMAL_BAKES:
        name='CMS_CMS_'+('HeadNode' if base=='emblem' else 'ROOT')+'_'+base
        low=lows[name];sources=[highs[name]]
        if base=='leather':sources.append(highs[REMOVED_MESH])
        old_alpha=pixel_array(bpy.data.images[f'cms_{base}_n.png'])[:,:,3].copy()
        normal=bake(low,sources,'NORMAL',base+'_n')
        if base=='leather':
            diffuse=bake(low,sources,'DIFFUSE','leather_d')
            spec=bake_alpha(low,sources)
            textures.append(install_image(diffuse,'cms_leather_d.png',a.textures,np.ones((1024,1024))))
        else:spec=old_alpha
        textures.append(install_image(normal,f'cms_{base}_n.png',a.textures,spec))
    for name,high in highs.items():destroy(high)
    for original in cms['meshes']:
        name=original['name']
        if name==REMOVED_MESH:continue
        low=lows[name];low.name=name;low.data.name=name
        original_material='CMS_'+low.active_material.name.split('CMS_',1)[1].split('.')[0]
        mat=low.active_material
        old=bpy.data.materials.get(original_material)
        if old and old!=mat and old.users==0:bpy.data.materials.remove(old)
        mat.name=original_material
    # Consolidate the copies back to the original 11 material identities.
    for obj in lows.values():
        mat=obj.active_material;canonical='CMS_'+mat.name.split('CMS_',1)[1].split('.')[0]
        target=bpy.data.materials.get(canonical)
        if target and target!=mat:
            obj.data.materials[0]=target
            if mat.users==0:bpy.data.materials.remove(mat)
        else:mat.name=canonical
    bpy.data.collections.remove(high_collection)
    for name in ('cms_cord_d.png','cms_cord_n.png'):bpy.data.images[name].use_fake_user=True
    manifest=dict(format='audit6-cord-bake-v1',baseline_cms_sha256=BASELINE_SHA256,
                  baseline_commit=AUDIT6_COMMIT,surface_limit_mm=SURFACE_LIMIT_M*1000,
                  source_blend_sha256=sha256(a.blend.read_bytes()),removed_mesh=REMOVED_MESH,
                  texture_bakes=textures,meshes=reports,
                  before_triangles=sum(len(m['faces']) for m in cms['meshes']),
                  after_triangles=sum(r['after_triangles'] for r in reports),
                  runtime_tested=False,xedit_tested=False)
    text=bpy.data.texts.get('AUDIT6_OPTIMIZATION.json') or bpy.data.texts.new('AUDIT6_OPTIMIZATION.json')
    text.clear();text.write(json.dumps(manifest,indent=2))
    bpy.context.scene['cms_optimization']='audit6-cord-bake-v1'
    bpy.context.scene['cms_workflow']='Use export_optimized_visuals.py; do not regenerate authored geometry.'
    bpy.context.scene.render.bake.use_selected_to_active=False
    select([lows['CMS_CMS_ROOT_leather']],lows['CMS_CMS_ROOT_leather'])
    bpy.context.scene.camera=bpy.data.objects['Preview_Front']
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()))
    a.out.with_suffix('.optimization.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('OPTIMIZATION_PASS',manifest['before_triangles'],manifest['after_triangles'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blend',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--textures',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);optimize(a)
