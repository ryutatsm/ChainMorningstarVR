"""Pinned root-only repair: all 14 six-sided bases lie inside the actual core.

Use the intersection of inward triangle half-spaces as a conservative interior.
Every base vertex is at least 0.35 mm behind every core face plane. Linearity
proves the entire base polygon/edges are inside, not just sparse samples. Only
translation of the bottom ring along its original spike axis is permitted.
"""
from pathlib import Path
import numpy as np
from cms_io import load, sha256
from leather_edge_contract import validate_rows as validate_leather, LEATHER, validate_unchanged

POLICY = 'spike-root-core-contact-v1'
SPIKE = 'CMS_CMS_HeadNode_spike'
CORE = 'CMS_CMS_HeadNode_metal'
SOURCE_SHA256 = '76e945ab472b49e233eb5931270768f95381222158c5b16321cecbaeef556a2b'
INSET_M = .00035
MAX_ROOT_MOVE_M = .010


def source():
    path = Path(__file__).parent / 'contracts/spike_contact_source.cms'
    if sha256(path.read_bytes()) != SOURCE_SHA256:
        raise ValueError('Spike contact source hash changed')
    return load(path, False)


def mesh(cms, name):
    return next(m for m in cms['meshes'] if m['name'] == name)


def components(rows, faces):
    # UV/normal seams split CMS vertices; weld position only for connectivity.
    _, inverse = np.unique(np.round(rows[:, :3], 7), axis=0, return_inverse=True)
    parent = np.arange(inverse.max() + 1)
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for face in inverse[faces]:
        for a, b in zip(face, face[1:]):
            parent[root(b)] = root(a)
    labels = np.array([root(i) for i in inverse])
    groups = [np.flatnonzero(labels == label) for label in sorted(set(labels))]
    # Stable direction ordering independent of CMS seam vertex ordering.
    groups.sort(key=lambda ids: tuple(np.round(rows[ids, :3].mean(0), 7)))
    if len(groups) != 14:
        raise ValueError('Expected 14 separate spikes')
    return groups


def planes(core):
    rows = np.array(core['vertices']); faces = np.array(core['faces'])
    triangles = rows[faces, :3]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    offsets = np.sum(normals * triangles[:, 0], axis=1)
    if np.any(offsets <= .08) or len(faces) != 224:
        raise ValueError('Core is not the pinned outward closed radial surface')
    # Connected, closed two-manifold after position welding.
    _, inverse = np.unique(np.round(rows[:, :3], 7), axis=0, return_inverse=True)
    edges = np.sort(np.concatenate([inverse[faces[:, [i, (i+1)%3]]] for i in range(3)]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    if np.any(counts != 2):
        raise ValueError('Core is not closed')
    return normals, offsets


def build(cms=None):
    cms = cms or source(); original = mesh(cms, SPIKE)
    rows = np.array(original['vertices']); faces = np.array(original['faces'])
    result = rows.copy(); normals, offsets = planes(mesh(cms, CORE))
    records = []
    for ids in components(rows, faces):
        bottom = ids[np.isclose(rows[ids, 7], rows[ids, 7].min(), atol=1e-8)]
        top = ids[np.isclose(rows[ids, 7], 1., atol=1e-8)]
        # Average unique ring vertices, avoiding UV/normal seam weighting.
        _, unique_ids = np.unique(np.round(rows[bottom, :3], 7), axis=0, return_index=True)
        ring = rows[bottom[unique_ids], :3]
        if len(ring) != 6 or len(bottom) + len(top) != len(ids):
            raise ValueError('Wrong two-ring six-sided spike topology')
        axis = ring.mean(0); axis /= np.linalg.norm(axis)
        signed = rows[bottom, :3] @ normals.T - offsets
        projection = normals @ axis
        forward = projection > 1e-8
        movement = max(0., float(np.max((signed[:, forward] + INSET_M) / projection[forward])))
        # Explicitly bounded, shape-preserving extension of each buried base.
        if movement > MAX_ROOT_MOVE_M:
            raise ValueError('Required root repair exceeds 10 mm scope')
        result[bottom, :3] -= movement * axis
        after_signed = result[bottom, :3] @ normals.T - offsets
        if after_signed.max() > -INSET_M + 1e-10:
            raise ValueError('Spike base cannot be embedded along its original axis')
        records.append(dict(axis=np.round(axis, 12).tolist(), before_maximum_plane_gap_mm=round(float(signed.max()*1000), 9),
                            root_extension_mm=round(movement*1000, 9),
                            after_maximum_plane_gap_mm=round(float(after_signed.max()*1000), 9)))
    proof = dict(policy=POLICY, source_cms_sha256=SOURCE_SHA256, spike_count=14,
                 inset_mm=INSET_M*1000, maximum_allowed_root_extension_mm=MAX_ROOT_MOVE_M*1000,
                 maximum_actual_root_extension_mm=max(r['root_extension_mm'] for r in records),
                 minimum_base_plane_clearance_mm=-max(r['after_maximum_plane_gap_mm'] for r in records),
                 entire_base_polygon_inside_core=True, proof='all vertices behind every outward face plane; convexity of half-space intersection covers complete base polygons',
                 tip_positions_uv_normals_preserved=True, base_width_uv_normals_preserved=True,
                 faces_and_triangle_count_preserved=True, all_other_meshes_unchanged=True,
                 spikes=records)
    return result, faces, proof


def validate_rows(rows, faces):
    expected, triangles, proof = build()
    actual = np.array(rows)[np.array(faces)]
    wanted = expected[triangles]
    if (actual.shape != wanted.shape or
        not np.allclose(actual[:, :, :3], wanted[:, :, :3], atol=1e-7, rtol=0) or
        not np.allclose(actual[:, :, 6:8], wanted[:, :, 6:8], atol=1e-7, rtol=0) or
        not np.allclose(actual[:, :, 3:6], wanted[:, :, 3:6], atol=1e-4, rtol=0)):
        raise ValueError('Spike roots/tips/UV/normals differ from the reviewed contact repair')
    # Verify actual exported coordinates independently (float32 Blender storage).
    normals, offsets = planes(mesh(source(), CORE))
    actual_rows = np.array(rows)
    for ids in components(actual_rows, np.array(faces)):
        bottom = ids[np.isclose(actual_rows[ids, 7], actual_rows[ids, 7].min(), atol=1e-8)]
        if (actual_rows[bottom, :3] @ normals.T - offsets).max() > -INSET_M + 1e-7:
            raise ValueError('Exported spike base floats outside actual core')
    return proof


def canonical_rows(rows, faces):
    """Restore exact pinned custom normals after Blender's <0.008-degree encoding.

    Positions come from actual exported corners; never substitute target geometry.
    Keep original seam indices and UV/normal bytes. Validation must precede this.
    """
    validate_rows(rows, faces)
    result, triangles, _ = build()
    corners = np.array(rows)[np.array(faces)]
    filled = set()
    for face, values in zip(triangles, corners):
        for index, value in zip(face, values):
            if index in filled and not np.allclose(result[index,:3], value[:3], atol=1e-8, rtol=0):
                raise ValueError('Inconsistent spike seam position')
            result[index,:3] = value[:3]; filled.add(int(index))
    return result, triangles


def validate_cms(cms):
    old = source(); proof = None
    if cms['nodes'] != old['nodes'] or cms['hulls'] != old['hulls']:
        raise ValueError('Spike repair changed runtime nodes/collision')
    if [(m['name'],m['parent'],m['material']) for m in cms['meshes']] != [(m['name'],m['parent'],m['material']) for m in old['meshes']]:
        raise ValueError('Spike repair changed mesh inventory')
    for m in cms['meshes']:
        if m['name'] == SPIKE:
            proof = validate_rows(m['vertices'], m['faces'])
            original=mesh(old,SPIKE);actual=np.array(m['vertices']);wanted=np.array(original['vertices'])
            if (m['faces'] != original['faces'] or actual.shape != wanted.shape or
                not np.array_equal(actual[:,3:8],wanted[:,3:8]) or
                not np.array_equal(actual[actual[:,7]==1,:3],wanted[wanted[:,7]==1,:3])):
                raise ValueError('Canonical spike normals/UV/tips/seams changed')
        else:
            validate_unchanged(m, mesh(old, m['name']))
    validate_leather(mesh(cms, LEATHER)['vertices'], mesh(cms, LEATHER)['faces'])
    if proof is None:
        raise ValueError('Missing spike repair')
    return proof
