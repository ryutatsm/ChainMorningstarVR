"""Blender 4.5: import verified audit6 CMS without glTF axis conversions.

blender --background --python Tools/Blender/create_project.py --
  --cms INPUT --manifest INPUT --textures PNG_DIRECTORY --out OUTPUT.blend
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cms_io import load, MATERIALS, BASELINE_SHA256, AUDIT6_COMMIT
import bpy
import bmesh
from mathutils import Matrix, Vector


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('cms', 'manifest', 'textures', 'out'):
        p.add_argument('--' + arg, type=Path, required=True)
    p.add_argument('--render', type=Path)
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    return p.parse_args(args)


def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def material(name, textures):
    base = 'metal' if name in ('darksteel', 'edge', 'bronze') else name
    m = bpy.data.materials.new('CMS_' + name)
    m['cms_material_index'] = MATERIALS.index(name)
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    shader = nodes.get('Principled BSDF')
    metal = name not in ('wood', 'leather', 'cord')
    shader.inputs['Metallic'].default_value = .85 if metal else 0
    shader.inputs['Roughness'].default_value = .48 if metal else .78
    for kind in ('d', 'n'):
        filename = f'cms_{base}_{kind}.png'
        im = bpy.data.images.get(filename) or bpy.data.images.load(str(textures / filename))
        im.colorspace_settings.name = 'sRGB' if kind == 'd' else 'Non-Color'
        if not im.packed_file:
            im.pack()
        im.filepath = '//textures/' + f'cms_{base}_{kind}.png'
        tex = nodes.new('ShaderNodeTexImage'); tex.image = im
        tex.label = 'Diffuse' if kind == 'd' else 'Normal RGB / specular alpha (not opacity)'
        tex.location = (-600, 180 if kind == 'd' else -140)
        if kind == 'd':
            if name in ('darksteel', 'bronze'):
                multiply = nodes.new('ShaderNodeMixRGB'); multiply.blend_type = 'MULTIPLY'
                multiply.inputs[0].default_value = 1
                multiply.inputs[2].default_value = (.31,.33,.35,1) if name == 'darksteel' else (1,.76,.44,1)
                links.new(tex.outputs['Color'], multiply.inputs[1])
                links.new(multiply.outputs[0], shader.inputs['Base Color'])
            else:
                links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        else:
            normal = nodes.new('ShaderNodeNormalMap'); normal.location = (-270, -140)
            links.new(tex.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    m['preview_only'] = 'Principled preview; NIF uses export_reference_nif.cpp shaders'
    return m


def camera(c, name, at, target, scale):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data); c.objects.link(obj)
    obj.location = at
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'; data.ortho_scale = scale
    return obj


def build(a):
    cms = load(a.cms)
    manifest = json.loads(a.manifest.read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.length_unit = 'METERS'
    scene.unit_settings.scale_length = 1
    scene['cms_baseline_commit'] = AUDIT6_COMMIT
    scene['cms_baseline_sha256'] = BASELINE_SHA256
    scene['cms_workflow'] = 'Edit mesh vertices/UVs; preserve named empties and collision. Read handoff.'
    node_collection = collection('01_Runtime_nodes_KEEP')
    visuals = collection('02_Visuals_EDIT')
    collisions = collection('03_Collision_reference_KEEP')
    staging = collection('04_Preview_lights_cameras_ONLY')
    mats = [material(n, a.textures) for n in MATERIALS]
    for path in sorted(a.textures.glob('*_m.png')):
        im = bpy.data.images.load(str(path), check_existing=True)
        im.colorspace_settings.name = 'Non-Color'; im.use_fake_user = True
        im.pack(); im.filepath = '//textures/' + path.name
    nodes = []
    for i, n in enumerate(cms['nodes']):
        ob = bpy.data.objects.new(n['name'], None); node_collection.objects.link(ob)
        mat = Matrix([n['r'][j:j+3] for j in (0,3,6)]).to_4x4()
        mat.translation = Vector(n['t'])
        if n['parent'] >= 0:
            ob.parent = nodes[n['parent']]
        ob.matrix_basis = mat
        ob.empty_display_type = 'PLAIN_AXES'; ob.empty_display_size = .014
        ob['cms_node_index'] = i
        ob.lock_location = (True,)*3; ob.lock_rotation = (True,)*3; ob.lock_scale = (True,)*3
        nodes.append(ob)
    for i, m in enumerate(cms['meshes']):
        mesh = bpy.data.meshes.new(m['name'])
        mesh.from_pydata([v[:3] for v in m['vertices']], [], m['faces']); mesh.update()
        uv = mesh.uv_layers.new(name='CMS_UV')
        for loop in mesh.loops:
            uv.data[loop.index].uv = m['vertices'][loop.vertex_index][6:8]
        for p in mesh.polygons:
            p.use_smooth = True
        mesh.normals_split_custom_set_from_vertices([v[3:6] for v in m['vertices']])
        ob = bpy.data.objects.new(m['name'], mesh); visuals.objects.link(ob)
        ob.parent = nodes[m['parent']]
        ob.data.materials.append(mats[m['material']])
        ob['cms_mesh_index'] = i
        ob['cms_edit_hint'] = 'Edit Mode / sculpt without Dyntopo. Exporter checks topology, units, hierarchy.'
        ob.lock_location = (True,)*3; ob.lock_rotation = (True,)*3; ob.lock_scale = (True,)*3
        for f in manifest['sculpt_features']:
            if f['parent'] == m['parent'] and MATERIALS.index(f['material']) == m['material']:
                group = ob.vertex_groups.new(name=f['name'])
                group.add(list(range(f['vertex_start'], f['vertex_start']+f['vertex_count'])), 1, 'REPLACE')
    for i, h in enumerate(cms['hulls']):
        mesh = bpy.data.meshes.new(f'CollisionHull_{i:02}')
        bm = bmesh.new()
        for v in h['vertices']: bm.verts.new(v)
        bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        bm.to_mesh(mesh); bm.free()
        ob = bpy.data.objects.new(mesh.name, mesh); collisions.objects.link(ob)
        ob.parent = nodes[-1]; ob.display_type = 'WIRE'; ob.show_in_front = True
        ob.hide_render = True; ob.hide_set(True)
        ob['cms_reference_only'] = True
    for ob in nodes: ob.hide_set(True)
    scene.camera = camera(staging, 'Preview_Front', (0,.65,3), (0,.65,0), 1.88)
    camera(staging, 'Preview_Head', (0,1.34,2), (0,1.34,0), .46)
    camera(staging, 'Preview_Handle', (0,.04,2), (0,.04,0), .56)
    for name, loc, energy, size in [('Key',(-1,1,2),130,2), ('Fill',(1,0,1.5),85,1.5), ('Rim',(0,1.2,-1),100,1.3)]:
        data=bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size
        ob=bpy.data.objects.new(name,data); staging.objects.link(ob); ob.location=loc
        ob.rotation_euler=(Vector((0,.65,0))-ob.location).to_track_quat('-Z','Y').to_euler()
    scene.world = bpy.data.worlds.new('Neutral_studio'); scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.07,.075,.085,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x=560; scene.render.resolution_y=1400; scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    for name, content in [('AUDIT6_BASELINE.cms', cms['data'].decode('utf-8')),
                          ('AUDIT6_ASSET_MANIFEST.json', json.dumps(manifest,ensure_ascii=False,indent=2)),
                          ('READ_ME_FIRST.txt', 'Audit6 visual-edit project. 1 Blender unit = 1 meter.\n'
                           'Mesh vertices/UVs are editable. Runtime empties and collision stay fixed.\n'
                           'Materials are previews; changing a shader does not change Skyrim.\n'
                           'Physics runs in the DLL, not in Blender. No rigid-body simulation here.\n'
                           'Use Tools/Blender/export_visual_edits.py from the handoff Git branch.\n')]:
        text = bpy.data.texts.new(name); text.write(content)
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='MATERIAL'
    bpy.ops.object.select_all(action='DESELECT')
    head = bpy.data.objects.get('CMS_CMS_HeadNode_metal')
    head.select_set(True); bpy.context.view_layer.objects.active=head
    a.out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()), compress=True)
    if a.render:
        a.render.parent.mkdir(parents=True,exist_ok=True)
        scene.render.filepath=str(a.render.resolve()); bpy.ops.render.render(write_still=True)
    print('BLENDER_PROJECT_PASS', len(cms['meshes']), 'meshes;',len(cms['nodes']),'runtime nodes;',a.out)


if __name__=='__main__':
    build(arguments())
