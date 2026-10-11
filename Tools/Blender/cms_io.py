"""Lossless CMSMESH 1 reader used by the Blender 4.5 handoff tools."""
from pathlib import Path
import hashlib

AUDIT6_COMMIT = "df3ef906a7927516263b567817900cc125d5f860"
BASELINE_SHA256 = "0319d497343fc72afa85f68ac5c3444df4042ac920633aea96eebe19e1d3ca57"
MATERIALS = ['metal', 'wood', 'leather', 'darksteel', 'edge', 'cord',
             'bronze', 'spike', 'chain', 'ring', 'emblem']


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse(data, require_baseline=True):
    if require_baseline and sha256(data) != BASELINE_SHA256:
        raise ValueError('Expected the verified audit6 CMS, not an older build')
    lines = data.decode('utf-8').splitlines(keepends=True)
    if lines[0].strip() != 'CMSMESH 1':
        raise ValueError('Unsupported CMS version')
    nn, nm, nh = map(int, lines[1].split())
    cursor = 2
    nodes, meshes, hulls = [], [], []
    for _ in range(nn):
        a = lines[cursor].split(); cursor += 1
        nodes.append(dict(name=a[0], parent=int(a[1]),
                          t=list(map(float, a[2:5])), r=list(map(float, a[5:14]))))
    for _ in range(nm):
        start = cursor
        name, parent, mat, nv, nt = lines[cursor].split(); cursor += 1
        nv, nt = int(nv), int(nt)
        vertices = [list(map(float, line.split())) for line in lines[cursor:cursor+nv]]
        cursor += nv
        faces = [tuple(map(int, line.split())) for line in lines[cursor:cursor+nt]]
        cursor += nt
        meshes.append(dict(name=name, parent=int(parent), material=int(mat),
                           vertices=vertices, faces=faces, start=start, end=cursor))
    collision_start = cursor
    for _ in range(nh):
        nv, np, margin = lines[cursor].split(); cursor += 1
        vertices = [list(map(float, a.split())) for a in lines[cursor:cursor+int(nv)]]
        cursor += int(nv)
        planes = [list(map(float, a.split())) for a in lines[cursor:cursor+int(np)]]
        cursor += int(np)
        hulls.append(dict(vertices=vertices, planes=planes, margin=float(margin)))
    if any(x.strip() for x in lines[cursor:]):
        raise ValueError('Unexpected trailing CMS records')
    return dict(data=data, lines=lines, nodes=nodes, meshes=meshes, hulls=hulls,
                collision_start=collision_start)


def load(path, require_baseline=True):
    return parse(Path(path).read_bytes(), require_baseline)
