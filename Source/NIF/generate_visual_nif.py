"""
Generate ChainMorningstarVR's Skyrim SE/VR NIF from scratch.

This deliberately does not import or clone any previous Chain Morningstar mod.
All dimensions below are the current project's own 2x design dimensions.

Coordinate convention:
  Skyrim weapon root: +Y is the weapon's long axis.
  CMS_ChainAnchor local +Z is rotated onto root +Y so the SKSE runtime can
  continue to use local +Z as the chain's tangent axis.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

SU_PER_M = 69.99125

# Current new-project dimensions.
HANDLE_LENGTH_M = 0.560
HANDLE_MIN_Y_M = -0.160
HANDLE_MAX_Y_M = HANDLE_MIN_Y_M + HANDLE_LENGTH_M  # +0.400
CHAIN_ANCHOR_Y_M = HANDLE_MAX_Y_M

LINK_COUNT = 14
FIRST_LINK_CENTER_M = 0.035
LINK_CENTER_SPAN_M = 0.840
HEAD_CENTER_FROM_ANCHOR_M = 1.065

HEAD_CORE_RADIUS_M = 0.160
SPIKE_INNER_AXIS_M = 0.154
SPIKE_OUTER_AXIS_M = 0.240
SPIKE_BASE_RADIUS_M = 0.046

LINK_MAJOR_RADIUS_M = 0.045
LINK_TUBE_RADIUS_M = 0.0105
LINK_LONG_AXIS_SCALE = 1.34

TEXTURE_ROOT = r"textures\weapons\ChainMorningstarVR"
TEX_METAL_D = TEXTURE_ROOT + r"\cms_metal_d.dds"
TEX_METAL_N = TEXTURE_ROOT + r"\cms_metal_n.dds"
TEX_METAL_M = TEXTURE_ROOT + r"\cms_metal_m.dds"
TEX_WOOD_D = TEXTURE_ROOT + r"\cms_wood_d.dds"
TEX_WOOD_N = TEXTURE_ROOT + r"\cms_wood_n.dds"
TEX_LEATHER_D = TEXTURE_ROOT + r"\cms_leather_d.dds"
TEX_LEATHER_N = TEXTURE_ROOT + r"\cms_leather_n.dds"
# Vanilla cubemap path; the mod does not redistribute this Bethesda asset.
TEX_CUBEMAP = r"textures\cubemaps\ore_e.dds"


def su(m: float) -> float:
    return m * SU_PER_M


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
        # Orphan purge is intentionally conservative; only delete unused blocks.
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def make_nif_node(name: str, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = su(0.035)
    obj.location = location
    obj.rotation_euler = rotation
    if parent is not None:
        obj.parent = parent
    obj["pynBlockName"] = "NiNode"
    obj["pynNodeName"] = name
    obj["pynNodeFlags"] = "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF"
    return obj


def make_root():
    root = bpy.data.objects.new("CMS_ROOT", None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = su(0.05)
    root["pynRoot"] = True
    root["pynBlockName"] = "BSFadeNode"
    root["pynNodeName"] = "ChainMorningstar.nif"
    root["pynNodeFlags"] = (
        "SELECTIVE_UPDATE | SELECTIVE_UPDATE_TRANSF | SELECTIVE_UPDATE_CONTR"
    )
    return root


def make_material(name: str, diffuse: str, normal: str, *, metal=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat["BS_Shader_Block_Name"] = "BSLightingShaderProperty"
    mat["BSShaderTextureSet_Diffuse"] = diffuse
    mat["BSShaderTextureSet_Normal"] = normal
    if metal:
        mat["BSShaderTextureSet_EnvMap"] = TEX_CUBEMAP
        mat["BSShaderTextureSet_EnvMask"] = TEX_METAL_M

    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    if not out.inputs["Surface"].is_linked:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Preview-only values. NIF shader values are normalized again after export.
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.86 if metal else 0.0
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.31 if metal else 0.56
    return mat


def assign_material(obj, material) -> None:
    if obj.type == "MESH":
        obj.data.materials.append(material)


def apply_all_transforms(obj) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


def cylinder_y(name, radius_m, length_m, center_y_m, material, vertices=32, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=su(radius_m),
        depth=su(length_m),
        location=(0.0, su(center_y_m), 0.0),
        rotation=(math.radians(-90.0), 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    apply_all_transforms(obj)
    if parent is not None:
        obj.parent = parent
    assign_material(obj, material)
    return obj


def uv_sphere(name, radius_m, material, parent=None, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=su(radius_m),
        location=(0, 0, 0),
    )
    obj = bpy.context.object
    obj.name = name
    if parent is not None:
        obj.parent = parent
    assign_material(obj, material)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def torus_link_mesh() -> bpy.types.Mesh:
    bpy.ops.mesh.primitive_torus_add(
        major_segments=20,
        minor_segments=8,
        location=(0, 0, 0),
        major_radius=su(LINK_MAJOR_RADIUS_M),
        minor_radius=su(LINK_TUBE_RADIUS_M),
        rotation=(math.radians(90.0), 0, 0),
    )
    obj = bpy.context.object
    obj.name = "_CMS_LinkTemplate"
    apply_all_transforms(obj)

    # Ring plane is XZ. Elongate the chain direction Z and slightly narrow X.
    for v in obj.data.vertices:
        v.co.z *= LINK_LONG_AXIS_SCALE
        v.co.x *= 0.82
    obj.data.update()

    mesh = obj.data.copy()
    bpy.data.objects.remove(obj, do_unlink=True)
    return mesh


def cone_along(name: str, direction: Vector, base_axis_m: float, tip_axis_m: float,
               base_radius_m: float, material, parent=None, segments=12):
    d = direction.normalized()
    depth = tip_axis_m - base_axis_m
    center = d * su((base_axis_m + tip_axis_m) * 0.5)
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=su(base_radius_m),
        radius2=0.0,
        depth=su(depth),
        location=center,
    )
    obj = bpy.context.object
    obj.name = name
    q = Vector((0, 0, 1)).rotation_difference(d)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = q
    apply_all_transforms(obj)
    if parent is not None:
        obj.parent = parent
    assign_material(obj, material)
    return obj


def join_objects(objects, name, parent=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    if parent is not None:
        obj.parent = parent
    return obj


def build_visual_scene():
    root = make_root()
    metal = make_material("CMS_Metal", TEX_METAL_D, TEX_METAL_N, metal=True)
    wood = make_material("CMS_Wood", TEX_WOOD_D, TEX_WOOD_N)
    leather = make_material("CMS_Leather", TEX_LEATHER_D, TEX_LEATHER_N)

    # Handle length is exactly 56 cm, with the NIF origin placed inside the grip
    # instead of at the pommel. That makes the VR hand attachment sensible while
    # preserving the requested physical handle length.
    handle_mid = (HANDLE_MIN_Y_M + HANDLE_MAX_Y_M) * 0.5
    cylinder_y("CMS_HandleWood", 0.030, HANDLE_LENGTH_M, handle_mid, wood, parent=root)

    # Leather grip around the NIF origin / hand region.
    cylinder_y("CMS_GripLeather", 0.0375, 0.245, 0.015, leather, parent=root)

    # Heavy steel collars and pommel.
    cylinder_y("CMS_LowerCollar", 0.045, 0.040, HANDLE_MIN_Y_M + 0.025, metal, parent=root)
    cylinder_y("CMS_UpperCollar", 0.048, 0.055, HANDLE_MAX_Y_M - 0.0275, metal, parent=root)

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=su(0.050),
        location=(0, su(HANDLE_MIN_Y_M - 0.030), 0)
    )
    pommel = bpy.context.object
    pommel.name = "CMS_Pommel"
    pommel.scale = (1.0, 0.72, 1.0)
    apply_all_transforms(pommel)
    pommel.parent = root
    assign_material(pommel, metal)

    # A thick eye/ring at the chain anchor.
    bpy.ops.mesh.primitive_torus_add(
        major_segments=24, minor_segments=8,
        major_radius=su(0.039), minor_radius=su(0.010),
        location=(0, su(CHAIN_ANCHOR_Y_M), 0),
        rotation=(math.radians(90.0), 0, 0),
    )
    eye = bpy.context.object
    eye.name = "CMS_ChainEye"
    apply_all_transforms(eye)
    eye.parent = root
    assign_material(eye, metal)

    # Anchor local +Z is rotated to root +Y. Runtime chain solver uses anchor +Z.
    anchor = make_nif_node(
        "CMS_ChainAnchor",
        parent=root,
        location=(0, su(CHAIN_ANCHOR_Y_M), 0),
        rotation=(math.radians(-90.0), 0, 0),
    )

    link_mesh = torus_link_mesh()
    spacing = LINK_CENTER_SPAN_M / (LINK_COUNT - 1)
    for i in range(LINK_COUNT):
        z_m = FIRST_LINK_CENTER_M + i * spacing
        node = make_nif_node(
            f"CMS_LinkNode_{i:02d}",
            parent=anchor,
            location=(0, 0, su(z_m)),
        )
        mesh_obj = bpy.data.objects.new(f"CMS_LinkMesh_{i:02d}", link_mesh.copy())
        bpy.context.collection.objects.link(mesh_obj)
        mesh_obj.parent = node
        assign_material(mesh_obj, metal)

    head = make_nif_node(
        "CMS_HeadNode",
        parent=anchor,
        location=(0, 0, su(HEAD_CENTER_FROM_ANCHOR_M)),
    )

    head_parts = [uv_sphere("CMS_HeadCoreVisual", HEAD_CORE_RADIUS_M, metal)]
    dirs = [
        Vector((1,0,0)), Vector((-1,0,0)),
        Vector((0,1,0)), Vector((0,-1,0)),
        Vector((0,0,1)), Vector((0,0,-1)),
    ]
    inv_sqrt3 = 1.0 / math.sqrt(3.0)
    for x in (-1,1):
        for y in (-1,1):
            for z in (-1,1):
                dirs.append(Vector((x*inv_sqrt3, y*inv_sqrt3, z*inv_sqrt3)))

    for i, d in enumerate(dirs):
        head_parts.append(cone_along(
            f"CMS_HeadSpikeVisual_{i:02d}", d,
            SPIKE_INNER_AXIS_M, SPIKE_OUTER_AXIS_M,
            SPIKE_BASE_RADIUS_M, metal
        ))
    head_mesh = join_objects(head_parts, "CMS_HeadMesh", parent=head)

    return root, anchor, head, dirs


def make_mesh_object(name: str, verts, faces, parent=None):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def cone_collision_geometry(direction: Vector, segments=8):
    d = direction.normalized()
    ref = Vector((0,0,1)) if abs(d.z) < 0.90 else Vector((0,1,0))
    u = ref.cross(d).normalized()
    v = d.cross(u).normalized()
    center = d * su(SPIKE_INNER_AXIS_M)
    radius = su(SPIKE_BASE_RADIUS_M)
    verts = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        p = center + u * (math.cos(a)*radius) + v * (math.sin(a)*radius)
        verts.append(tuple(p))
    tip = d * su(SPIKE_OUTER_AXIS_M)
    verts.append(tuple(tip))
    tip_i = len(verts)-1
    faces = []
    faces.append(tuple(reversed(range(segments))))
    for i in range(segments):
        faces.append((i, (i+1)%segments, tip_i))
    return verts, faces


def build_head_collision(head_node, dirs):
    from io_scene_nifly.nif import pyn_props

    # Collision list object lives at the head's initial world transform, but is not a
    # visual child. The head node references it through pynCollisionTarget.
    bpy.context.view_layer.update()
    verts = [(-0.001,-0.001,-0.001),(0.001,-0.001,-0.001),(0,0.001,-0.001),(0,0,0.001)]
    faces = [(0,1,2),(0,3,1),(1,3,2),(2,3,0)]
    list_obj = make_mesh_object("bhkListShape_CMSHead", verts, faces)
    list_obj.matrix_world = head_node.matrix_world.copy()
    list_obj["pynRigidBody"] = "bhkRigidBody"
    list_obj["pynCollisionBlockname"] = "bhkCollisionObject"

    pyn_props.set_collshape(list_obj, "HEAVY_METAL", 0.0)
    pyn_props.set_group(
        list_obj, "pyn_collisionobj",
        flags="ACTIVE | SYNC_ON_UPDATE"
    )

    bpy.ops.object.select_all(action="DESELECT")
    list_obj.select_set(True)
    bpy.context.view_layer.objects.active = list_obj
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    list_obj.rigid_body.mass = 8.0
    list_obj.rigid_body.friction = 0.74
    list_obj.rigid_body.restitution = 0.08
    list_obj.rigid_body.linear_damping = 0.12
    list_obj.rigid_body.angular_damping = 0.20
    list_obj.rigid_body.collision_shape = "COMPOUND"
    list_obj.rigid_body.use_margin = True
    list_obj.rigid_body.collision_margin = 0.004

    rb = list_obj.pyn_rigidbody
    # These are enum-name strings in PyNifly's generated property group.
    for attr, value in (
        ("collisionFilter_layer", "WEAPON"),
        ("collisionResponse", "SIMPLE_CONTACT"),
        ("collisionResponse2", "SIMPLE_CONTACT"),
        ("motionSystem", "SPHERE_STABILIZED"),
        ("solverDeactivation", "LOW"),
        ("qualityType", "MOVING"),
        ("broadPhaseType", "ENTITY"),
    ):
        if hasattr(rb, attr):
            try:
                setattr(rb, attr, value)
            except Exception as e:
                print(f"CMS_NIF: warning could not set rigid-body {attr}={value}: {e}")

    # Core collision: convex icosphere approximation, intentionally NOT one 24 cm
    # sphere. The 24 cm sweep radius exists only in the runtime broadphase.
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2,
        radius=su(HEAD_CORE_RADIUS_M),
        location=(0,0,0),
    )
    core = bpy.context.object
    core.name = "bhkConvexVerticesShape_CMSCore"
    # Reparent without changing local geometry/transforms.
    core.parent = list_obj
    core.matrix_parent_inverse = Matrix.Identity(4)
    core.location = (0,0,0)
    core.rotation_euler = (0,0,0)
    core.scale = (1,1,1)
    pyn_props.set_collshape(core, "HEAVY_METAL", 0.003)

    # 14 separately convex spikes. Geometry is baked in list-local coordinates and
    # object transforms remain identity, so PyNifly exports 15 bare list children
    # rather than fabricating bhkConvexTransformShape wrappers.
    for i, d in enumerate(dirs):
        sv, sf = cone_collision_geometry(d)
        spike = make_mesh_object(
            f"bhkConvexVerticesShape_CMSSpike_{i:02d}", sv, sf, parent=list_obj
        )
        spike.location = (0,0,0)
        spike.rotation_euler = (0,0,0)
        spike.scale = (1,1,1)
        pyn_props.set_collshape(spike, "HEAVY_METAL", 0.002)

    head_node["pynCollisionTarget"] = list_obj.name
    return list_obj


def patch_and_validate_nif(nif_path: Path):
    from io_scene_nifly.pyn.pynifly import NifFile
    from io_scene_nifly.pyn.nifconstants import ShaderFlags1

    nif = NifFile(str(nif_path))
    required_nodes = [
        "CMS_ChainAnchor",
        "CMS_HeadNode",
        *[f"CMS_LinkNode_{i:02d}" for i in range(LINK_COUNT)],
    ]
    missing = [n for n in required_nodes if n not in nif.nodes]
    if missing:
        raise RuntimeError(f"Missing required NIF nodes: {missing}")

    anchor = nif.nodes["CMS_ChainAnchor"]
    # Root origin is inside the grip; anchor sits at +40 cm root Y.
    want_anchor_y = su(CHAIN_ANCHOR_Y_M)
    got = anchor.transform.translation
    if abs(got[1] - want_anchor_y) > 0.15:
        raise RuntimeError(
            f"CMS_ChainAnchor Y mismatch: got {got[1]:.4f}, want {want_anchor_y:.4f}"
        )

    # Runtime ABI dimensions must survive the NIF export exactly enough for the
    # 90 Hz solver to address the same geometry it was designed for.
    first_link = nif.nodes["CMS_LinkNode_00"].transform.translation
    last_link = nif.nodes["CMS_LinkNode_13"].transform.translation
    head_local = nif.nodes["CMS_HeadNode"].transform.translation

    want_first_z = su(FIRST_LINK_CENTER_M)
    want_last_z = su(FIRST_LINK_CENTER_M + LINK_CENTER_SPAN_M)
    want_head_z = su(HEAD_CENTER_FROM_ANCHOR_M)
    for label, got, want in (
        ("first link Z", first_link[2], want_first_z),
        ("last link Z", last_link[2], want_last_z),
        ("head Z", head_local[2], want_head_z),
    ):
        if abs(got - want) > 0.15:
            raise RuntimeError(f"{label} mismatch: got {got:.4f}, want {want:.4f}")

    span_m = (last_link[2] - first_link[2]) / SU_PER_M
    head_reach_m = head_local[2] / SU_PER_M
    if abs(span_m - 0.840) > 0.002:
        raise RuntimeError(f"Link-centre span mismatch: {span_m:.6f}m")
    if abs(head_reach_m - 1.065) > 0.002:
        raise RuntimeError(f"Head-centre reach mismatch: {head_reach_m:.6f}m")

    print(
        f"CMS_NIF_DIMENSIONS_OK handle={HANDLE_LENGTH_M:.3f}m "
        f"link_span={span_m:.3f}m head_reach={head_reach_m:.3f}m"
    )

    head_node = nif.nodes["CMS_HeadNode"]
    coll = head_node.collision_object
    if coll is None or coll.body is None or coll.body.shape is None:
        raise RuntimeError("CMS_HeadNode collision hierarchy missing")
    if coll.body.shape.blockname != "bhkListShape":
        raise RuntimeError(
            f"Expected bhkListShape, got {coll.body.shape.blockname}"
        )
    children = list(coll.body.shape.children)
    if len(children) != 15:
        raise RuntimeError(
            f"Expected 15 head collision children (core+14 spikes), got {len(children)}"
        )
    names = [c.blockname for c in children]
    if any(n != "bhkConvexVerticesShape" for n in names):
        raise RuntimeError(f"Unexpected head collision child blocks: {names}")

    # PyNifly exposes Skyrim Havok convex vertices in meter-like Havok units.
    # The head must be one ~16 cm core plus fourteen spikes whose tips reach 24 cm.
    radii = []
    for child in children:
        verts = list(child.vertices)
        if not verts:
            raise RuntimeError("Head collision child has no vertices")
        rmax = max(math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]) for v in verts)
        radii.append(rmax)
    radii.sort()
    core_radius = radii[0]
    spike_radii = radii[1:]
    if abs(core_radius - HEAD_CORE_RADIUS_M) > 0.008:
        raise RuntimeError(
            f"Head core collision radius mismatch: {core_radius:.6f}m"
        )
    if len(spike_radii) != 14 or any(abs(r - SPIKE_OUTER_AXIS_M) > 0.008 for r in spike_radii):
        raise RuntimeError(
            f"Head spike collision extents mismatch: {spike_radii}"
        )
    print(
        f"CMS_NIF_HEAD_EXTENTS_OK core={core_radius:.3f}m "
        f"spikes={min(spike_radii):.3f}..{max(spike_radii):.3f}m"
    )

    # Normalize shader settings after Blender export. Texture slots were already
    # written from material custom props; this guarantees a heavy metal response.
    for shape in nif.shapes:
        if not shape.shader:
            continue
        p = shape.shader.properties
        if shape.name.startswith(("CMS_Head", "CMS_Link", "CMS_UpperCollar",
                                  "CMS_LowerCollar", "CMS_Pommel", "CMS_ChainEye")):
            p.shaderflags1_set(ShaderFlags1.SPECULAR)
            p.shaderflags1_set(ShaderFlags1.ENVIRONMENT_MAPPING)
            p.Glossiness = 38.0
            p.Spec_Str = 2.15
            p.Spec_Color = (0.72, 0.76, 0.80)
            p.Env_Map_Scale = 0.82
            shape.set_texture("Diffuse", TEX_METAL_D)
            shape.set_texture("Normal", TEX_METAL_N)
            shape.set_texture("EnvMap", TEX_CUBEMAP)
            shape.set_texture("EnvMask", TEX_METAL_M)
        elif shape.name.startswith("CMS_HandleWood"):
            p.shaderflags1_set(ShaderFlags1.SPECULAR)
            p.Glossiness = 13.0
            p.Spec_Str = 0.42
            shape.set_texture("Diffuse", TEX_WOOD_D)
            shape.set_texture("Normal", TEX_WOOD_N)
        elif shape.name.startswith("CMS_GripLeather"):
            p.shaderflags1_set(ShaderFlags1.SPECULAR)
            p.Glossiness = 8.0
            p.Spec_Str = 0.28
            shape.set_texture("Diffuse", TEX_LEATHER_D)
            shape.set_texture("Normal", TEX_LEATHER_N)
        shape.shader.write_properties()

    nif.save()

    # Re-open the bytes that were actually written.
    check = NifFile(str(nif_path))
    head_check = check.nodes["CMS_HeadNode"]
    c2 = head_check.collision_object
    if not c2 or not c2.body or not c2.body.shape:
        raise RuntimeError("Round-trip collision missing")
    if c2.body.shape.blockname != "bhkListShape":
        raise RuntimeError("Round-trip head shape is not bhkListShape")
    if len(list(c2.body.shape.children)) != 15:
        raise RuntimeError("Round-trip head collision child count changed")

    # Ensure the old/incorrect broadphase-as-damage-sphere design cannot silently
    # come back: all actual damage-shape children must be convex core/spikes.
    if any(ch.blockname == "bhkSphereShape" for ch in c2.body.shape.children):
        raise RuntimeError("Release gate: broadphase sphere leaked into damage collision")

    print("CMS_NIF_VALIDATE: PASS")
    print(f"CMS_NIF_VALIDATE: nodes={len(check.nodes)} shapes={len(check.shapes)}")
    print("CMS_NIF_VALIDATE: head collision=bhkListShape children=15")


def output_path_from_env() -> Path:
    p = os.environ.get("CMS_NIF_OUT")
    if not p:
        raise RuntimeError("CMS_NIF_OUT environment variable is required")
    out = Path(p)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def main():
    out = output_path_from_env()
    print(f"CMS_NIF: Blender {bpy.app.version_string}")
    print(f"CMS_NIF: output={out}")

    clear_scene()
    root, anchor, head, dirs = build_visual_scene()
    build_head_collision(head, dirs)
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active = root

    result = bpy.ops.export_scene.pynifly(
        filepath=str(out),
        target_game="SKYRIMSE",
        preserve_hierarchy=True,
    )
    print(f"CMS_NIF: exporter result={result}")
    if not out.exists() or out.stat().st_size < 1024:
        raise RuntimeError("PyNifly did not produce a valid-sized NIF")

    patch_and_validate_nif(out)
    print(f"CMS_NIF: PASS size={out.stat().st_size}")


if __name__ == "__main__":
    main()
