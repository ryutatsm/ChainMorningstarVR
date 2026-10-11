"""Extend only the 14 existing base rings into the unchanged low-poly core."""
import argparse, json, sys
from pathlib import Path
import bpy, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spike_contact_contract import build, source, SPIKE
from cms_io import sha256


def finish(blend, out):
    bpy.ops.wm.open_mainfile(filepath=str(blend.resolve()))
    original = next(m for m in source()['meshes'] if m['name'] == SPIKE)
    old = np.array(original['vertices']); wanted, faces, proof = build()
    obj = bpy.data.objects[SPIKE]; changed = 0
    original_normals = [n.vector[:] for n in obj.data.corner_normals]
    for vertex in obj.data.vertices:
        ids = np.flatnonzero(np.linalg.norm(old[:, :3] - np.array(vertex.co), axis=1) < 1e-7)
        if not len(ids):
            raise ValueError('Blender spike differs from pinned input')
        target = wanted[ids[0], :3]
        if not np.allclose(wanted[ids, :3], target, atol=1e-7, rtol=0):
            raise ValueError('Ambiguous seam position')
        if np.linalg.norm(target - np.array(vertex.co)) > 1e-7:
            vertex.co = target; changed += 1
    if changed != 14*7:
        raise ValueError('Unexpected root vertex count: '+str(changed))
    obj.data.update()
    obj.data.normals_split_custom_set(original_normals)
    text = bpy.data.texts['AUDIT6_OPTIMIZATION.json']; manifest = json.loads(text.as_string())
    manifest['spike_contact_finish'] = proof
    manifest['spike_contact_source_blend_sha256'] = sha256(blend.read_bytes())
    text.clear(); text.write(json.dumps(manifest, indent=2))
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out.resolve()), compress=True)
    print('SPIKE_CONTACT_FINISH_PASS', changed, 'existing vertices moved; no new triangles', json.dumps(proof), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--blend', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:]); finish(a.blend, a.out)
