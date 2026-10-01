import bpy
import math
import os
import sys
from mathutils import Vector

SU_PER_M = 69.99125
HANDLE_M = 0.56
LINK_COUNT = 14
FIRST_LINK_M = 0.035
LINK_SPAN_M = 0.84
HEAD_FROM_LAST_M = 0.19
CORE_RADIUS_M = 0.16
SPIKE_LENGTH_M = 0.08
SPIKE_BASE_RADIUS_M = 0.046

HANDLE = HANDLE_M * SU_PER_M
FIRST = FIRST_LINK_M * SU_PER_M
SPAN = LINK_SPAN_M * SU_PER_M
HEAD_FROM_LAST = HEAD_FROM_LAST_M * SU_PER_M
CORE_R = CORE_RADIUS_M * SU_PER_M
SPIKE_L = SPIKE_LENGTH_M * SU_PER_M
SPIKE_BASE_R = SPIKE_BASE_RADIUS_M * SU_PER_M

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def mat(name, rgba, metallic=0.0, roughness=0.5):
    m=bpy.data.materials.new(name)
    m.diffuse_color=rgba
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value=rgba
        bsdf.inputs['Metallic'].default_value=metallic
        bsdf.inputs['Roughness'].default_value=roughness
    return m

def add_empty(name, loc=(0,0,0), parent=None):
    o=bpy.data.objects.new(name,None)
    bpy.context.collection.objects.link(o)
    o.location=loc
    if parent:
        o.parent=parent
    return o

def parent_keep_world(obj,parent):
    mw=obj.matrix_world.copy()
    obj.parent=parent
    obj.matrix_world=mw

def add_cylinder(name,radius,depth,loc,material,vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o=bpy.context.object
    o.name=name
    o.data.name=name+'Mesh'
    o.data.materials.append(material)
    return o

def add_torus(name,major,minor,loc,rot,material):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor,
        major_segments=48, minor_segments=16,
        location=loc, rotation=rot)
    o=bpy.context.object
    o.name=name
    o.data.name=name+'Mesh'
    o.data.materials.append(material)
    return o

def add_ico(name,radius,loc,material):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4,radius=radius,location=loc)
    o=bpy.context.object
    o.name=name
    o.data.name=name+'Mesh'
    o.data.materials.append(material)
    return o

def add_spike(name,base_radius,length,core_radius,direction,head_center,material,parent):
    d=Vector(direction).normalized()
    center=Vector(head_center)+d*(core_radius+length*0.5)
    q=Vector((0,0,1)).rotation_difference(d)
    bpy.ops.mesh.primitive_cone_add(
        vertices=32, radius1=base_radius, radius2=0.18,
        depth=length, location=center, rotation=q.to_euler())
    o=bpy.context.object
    o.name=name
    o.data.name=name+'Mesh'
    o.data.materials.append(material)
    parent_keep_world(o,parent)
    return o


def mesh_object(name, verts, faces, parent=None):
    mesh=bpy.data.meshes.new(name+'Mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent=parent
    return obj

def add_rigidbody(obj, mass=1.0, friction=0.5, restitution=0.05, shape='CONVEX_HULL'):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.rigidbody.object_add(type='ACTIVE')
    obj.rigid_body.collision_shape=shape
    obj.rigid_body.mass=mass
    obj.rigid_body.friction=friction
    obj.rigid_body.restitution=restitution
    obj.rigid_body.linear_damping=0.08
    obj.rigid_body.angular_damping=0.12
    obj.rigid_body.use_margin=False

def collision_spike_mesh(direction, base_axis, tip_axis, base_radius, segments=16):
    d=Vector(direction).normalized()
    ref=Vector((0,0,1)) if abs(d.z)<0.9 else Vector((0,1,0))
    u=ref.cross(d).normalized()
    v=d.cross(u).normalized()
    bc=d*base_axis
    tip=d*tip_axis
    verts=[]
    for i in range(segments):
        a=2.0*math.pi*i/segments
        p=bc + (math.cos(a)*u + math.sin(a)*v)*base_radius
        verts.append(tuple(p))
    verts.append(tuple(tip))
    ti=segments
    faces=[tuple(reversed(range(segments)))]
    for i in range(segments):
        faces.append((i,(i+1)%segments,ti))
    return verts,faces

def create_head_collision(head, head_z):
    # PyNifly 29 can export bhkListShape + bhkConvexVerticesShape author-created
    # collisions. New bhkSphereShape export is still TODO, so the spherical core is
    # represented by a convex icosphere and the 14 visible spikes by 14 convex cones.
    from io_scene_nifly.nif import pyn_props
    from io_scene_nifly.pyn.nifconstants import (
        SkyrimCollisionLayer, SkyrimHavokMaterial, hkMotionType,
        hkSolverDeactivation, hkQualityType, hkResponseType)

    holder_mesh=bpy.data.meshes.new('bhkListShapeMesh')
    holder_mesh.from_pydata([(0,0,0)],[],[])
    holder_mesh.update()
    holder=bpy.data.objects.new('bhkListShape',holder_mesh)
    bpy.context.collection.objects.link(holder)
    holder.location=(0,0,head_z)
    holder.display_type='WIRE'
    holder.hide_render=True
    add_rigidbody(holder,mass=8.0,friction=0.58,restitution=0.06,shape='COMPOUND')

    # Collision-object and rigid-body settings for a moving weapon.
    pyn_props.set_group(holder,'pyn_collisionobj',flags='ACTIVE | SYNC_ON_UPDATE')
    pyn_props.set_collshape(holder,'HEAVY_METAL',0.0)
    holder['pynRigidBody']='bhkRigidBody'
    holder['collisionFilter_layer']=SkyrimCollisionLayer.WEAPON
    holder['collisionFilterCopy_layer']=SkyrimCollisionLayer.WEAPON
    holder['collisionResponse']=hkResponseType.SIMPLE_CONTACT
    holder['collisionResponse2']=hkResponseType.SIMPLE_CONTACT
    holder['motionSystem']=hkMotionType.SPHERE_STABILIZED
    holder['solverDeactivation']=hkSolverDeactivation.LOW
    holder['qualityType']=hkQualityType.MOVING
    holder['penetrationDepth']=0.08
    holder['rollingFrictionMult']=0.0
    holder['processContactCallbackDelay']=65535
    holder['processContactCallbackDelay2']=65535

    # Core collision: convex approximation of a true 16 cm-radius sphere.
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=CORE_R,location=(0,0,0))
    core=bpy.context.object
    core.name='bhkConvexVerticesShape'
    core.data.name=core.name+'Mesh'
    core.parent=holder
    core.location=(0,0,0)
    core.rotation_euler=(0,0,0)
    core.scale=(1,1,1)
    core.display_type='WIRE'
    core.hide_render=True
    pyn_props.set_collshape(core,'HEAVY_METAL',0.0)

    # Spike proxies deliberately overlap the core slightly so no seam can tunnel.
    base_axis=0.154*SU_PER_M
    tip_axis=(CORE_RADIUS_M+SPIKE_LENGTH_M)*SU_PER_M
    base_radius=SPIKE_BASE_RADIUS_M*SU_PER_M
    inv=1/math.sqrt(3)
    dirs=[
        (1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),
        (inv,inv,inv),(-inv,inv,inv),(inv,-inv,inv),(-inv,-inv,inv),
        (inv,inv,-inv),(-inv,inv,-inv),(inv,-inv,-inv),(-inv,-inv,-inv)
    ]
    spikes=[]
    for i,d in enumerate(dirs):
        verts,faces=collision_spike_mesh(d,base_axis,tip_axis,base_radius,16)
        s=mesh_object('bhkConvexVerticesShape',verts,faces,parent=holder)
        s.location=(0,0,0)
        s.rotation_euler=(0,0,0)
        s.scale=(1,1,1)
        s.display_type='WIRE'
        s.hide_render=True
        pyn_props.set_collshape(s,'HEAVY_METAL',0.0)
        spikes.append(s)

    # Collision is authored for THIS head node, not the root and not a vanilla mace node.
    con=head.constraints.new(type='COPY_TRANSFORMS')
    con.name='CMS_HeadCollisionConstraint'
    con.target=holder

    return holder,core,spikes


def build():
    clear_scene()
    metal=mat('CMS_Metal',(0.20,0.22,0.24,1.0),0.90,0.26)
    wood=mat('CMS_Wood',(0.16,0.07,0.025,1.0),0.0,0.48)
    leather=mat('CMS_Leather',(0.055,0.028,0.018,1.0),0.0,0.62)

    root=add_empty('ChainMorningstarRoot',(0,0,0))
    root['pynRoot']=True
    root['pynGame']='SKYRIMSE'

    # Handle: anchor sits at Z=0, handle extends downward-to-upward? For hand use,
    # the chain exits the top at Z=0 and the grip extends toward +Z.
    handle=add_cylinder('CMS_Handle_Wood',1.20,HANDLE,(0,0,HANDLE*0.5),wood)
    parent_keep_world(handle,root)

    grip=add_cylinder('CMS_Grip_Leather',1.34,HANDLE*0.56,(0,0,HANDLE*0.52),leather)
    parent_keep_world(grip,root)

    collar=add_cylinder('CMS_Head_Collar',1.85,2.4,(0,0,0.9),metal)
    parent_keep_world(collar,root)
    pommel=add_cylinder('CMS_Pommel',1.72,3.0,(0,0,HANDLE-1.2),metal)
    parent_keep_world(pommel,root)

    anchor=add_empty('CMS_ChainAnchor',(0,0,0),root)

    spacing=SPAN/(LINK_COUNT-1)
    link_major=0.042*SU_PER_M
    link_minor=0.0085*SU_PER_M
    for i in range(LINK_COUNT):
        z=-(FIRST + i*spacing)
        n=add_empty(f'CMS_LinkNode_{i:02d}',(0,0,z),anchor)
        rot=(math.pi/2, 0, (math.pi/2 if i%2 else 0))
        mesh=add_torus(f'CMS_LinkMesh_{i:02d}',link_major,link_minor,(0,0,z),rot,metal)
        parent_keep_world(mesh,n)

    last_z=-(FIRST+SPAN)
    head_z=last_z-HEAD_FROM_LAST
    head=add_empty('CMS_HeadNode',(0,0,head_z),anchor)
    core=add_ico('CMS_Head_Core',CORE_R,(0,0,head_z),metal)
    parent_keep_world(core,head)

    inv=1/math.sqrt(3)
    dirs=[
        (1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),
        (inv,inv,inv),(-inv,inv,inv),(inv,-inv,inv),(-inv,-inv,inv),
        (inv,inv,-inv),(-inv,inv,-inv),(inv,-inv,-inv),(-inv,-inv,-inv)
    ]
    for i,d in enumerate(dirs):
        add_spike(f'CMS_Head_Spike_{i:02d}',SPIKE_BASE_R,SPIKE_L,CORE_R,d,(0,0,head_z),metal,head)

    create_head_collision(head,head_z)

    # Smooth shading for forged metal silhouette.
    for o in bpy.context.scene.objects:
        if o.type=='MESH':
            for p in o.data.polygons:
                p.use_smooth=True

    return root

def export_and_roundtrip():
    root=build()
    out=os.environ.get('CMS_NIF_OUT')
    if not out:
        raise RuntimeError('CMS_NIF_OUT not set')
    os.makedirs(os.path.dirname(out),exist_ok=True)

    # Export only the root hierarchy. Collision helper meshes must NOT be selected as
    # ordinary visual shapes; PyNifly discovers them through CMS_HeadNode's
    # COPY_TRANSFORMS collision constraint.
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    result=bpy.ops.export_scene.pynifly(filepath=out,target_game='SKYRIMSE',preserve_hierarchy=True)
    if 'FINISHED' not in result:
        raise RuntimeError(f'PyNifly export failed: {result}')
    if not os.path.exists(out) or os.path.getsize(out)<1024:
        raise RuntimeError('NIF missing or implausibly small')

    # Inspect the actual on-disk NIF before Blender round-trip. This validates that
    # CMS_HeadNode owns the collision and that it is a 15-part narrow-phase shape.
    from io_scene_nifly.pyn.pynifly import NifFile
    from io_scene_nifly.pyn.nifconstants import SkyrimCollisionLayer
    nif=NifFile(out)
    headnode=nif.nodes.get('CMS_HeadNode')
    if headnode is None or headnode.collision_object is None:
        raise RuntimeError('CMS_HeadNode has no exported collision object')
    body=headnode.collision_object.body
    if body is None or body.shape is None:
        raise RuntimeError('CMS_HeadNode collision has no rigid body/shape')
    if body.properties.collisionFilter_layer != SkyrimCollisionLayer.WEAPON:
        raise RuntimeError(f'Head collision layer is not WEAPON: {body.properties.collisionFilter_layer}')
    if body.shape.blockname != 'bhkListShape':
        raise RuntimeError(f'Head collision is not bhkListShape: {body.shape.blockname}')
    children=list(body.shape.children)
    if len(children)!=15:
        raise RuntimeError(f'Head collision expected 15 narrow-phase children, got {len(children)}')
    bad=[x.blockname for x in children if x.blockname!='bhkConvexVerticesShape']
    if bad:
        raise RuntimeError('Unexpected head collision child types: '+', '.join(bad))
    print('CMS_HEAD_COLLISION_OK',body.shape.blockname,len(children),'layer',body.properties.collisionFilter_layer)

    # Round-trip with the same exporter/importer and verify the runtime ABI names.
    clear_scene()
    r=bpy.ops.import_scene.pynifly(filepath=out)
    if 'FINISHED' not in r:
        raise RuntimeError(f'PyNifly re-import failed: {r}')

    required=['CMS_ChainAnchor','CMS_HeadNode']+[f'CMS_LinkNode_{i:02d}' for i in range(14)]
    present={o.name.split(':')[0] for o in bpy.context.scene.objects}
    missing=[n for n in required if n not in present]
    if missing:
        raise RuntimeError('NIF round-trip lost runtime nodes: '+', '.join(missing))

    print('CMS_NIF_EXPORT_OK',out,os.path.getsize(out))
    print('CMS_NIF_RUNTIME_NODES_OK',len(required))

if __name__=='__main__':
    export_and_roundtrip()
