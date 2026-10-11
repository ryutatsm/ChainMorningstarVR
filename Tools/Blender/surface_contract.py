"""Blender-native quantitative checks for the explicit audit6 optimization route.

This is a dense sampled distance check, not a mathematical Hausdorff proof.
The original topology-preserving exporter remains a separate, stricter route.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SURFACE_LIMIT_M = .00015
REMOVED_MESH = 'CMS_CMS_ROOT_cord'
NORMAL_BAKES = ('wood', 'leather', 'emblem')


def surface(p, f):
    return BVHTree.FromPolygons([Vector(v) for v in p], np.asarray(f).tolist(), all_triangles=True)


def points(p, f):
    t = p[f]
    # Vertices, centroid, three edge midpoints and three interior quarter points.
    return np.concatenate([p, t.mean(1), (t[:,0]+t[:,1])*.5,
                           (t[:,1]+t[:,2])*.5, (t[:,0]+t[:,2])*.5,
                           t[:,0]*.5+t[:,1]*.25+t[:,2]*.25,
                           t[:,1]*.5+t[:,0]*.25+t[:,2]*.25,
                           t[:,2]*.5+t[:,0]*.25+t[:,1]*.25])


def distance_report(p, f, q, g):
    result = {}
    for key, tree, samples in [('original_to_edited',surface(q,g),points(p,f)),
                                ('edited_to_original',surface(p,f),points(q,g))]:
        d = np.asarray([tree.find_nearest(Vector(x))[3] for x in samples])
        result[key] = dict(samples=len(d),max_mm=float(d.max()*1000),
                           p99_mm=float(np.percentile(d,99)*1000),
                           rms_mm=float(np.sqrt(np.mean(d*d))*1000))
    return result


def maximum(report):
    return max(value['max_mm'] for value in report.values()) / 1000


def topology(p, f):
    """Weld position seams only for topology analysis; never discard export UVs."""
    keys = [tuple(np.rint(x/1e-7).astype(np.int64)) for x in p]
    unique = {}; remap = []
    for key in keys:
        if key not in unique: unique[key] = len(unique)
        remap.append(unique[key])
    faces = np.asarray(remap)[f]
    used = set(faces.ravel().tolist())
    adjacency = {v:set() for v in used}; edges = {}
    for tri in faces:
        for a,b in zip(tri, np.roll(tri,-1)):
            a,b=int(a),int(b)
            if a==b: raise ValueError('Degenerate welded triangle')
            k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
            adjacency[a].add(b);adjacency[b].add(a)
    components=0;unseen=set(used)
    while unseen:
        components+=1;stack=[unseen.pop()]
        while stack:
            for v in adjacency[stack.pop()]:
                if v in unseen: unseen.remove(v);stack.append(v)
    boundary={}
    for (a,b),n in edges.items():
        if n==1: boundary.setdefault(a,set()).add(b);boundary.setdefault(b,set()).add(a)
    boundary_components=0;unseen=set(boundary)
    while unseen:
        boundary_components+=1;stack=[unseen.pop()]
        while stack:
            for v in boundary[stack.pop()]:
                if v in unseen: unseen.remove(v);stack.append(v)
    return dict(components=components,euler=len(used)-len(edges)+len(faces),
                boundary_components=boundary_components,
                nonmanifold_edges=sum(n>2 for n in edges.values()))


def orientation(p, f, q, g):
    tree=surface(p,f);old=np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]])
    new=np.cross(q[g[:,1]]-q[g[:,0]],q[g[:,2]]-q[g[:,0]])
    if np.any(np.linalg.norm(new,axis=1)<1e-13): raise ValueError('Degenerate edited triangle')
    dots=[]
    for center,n in zip(q[g].mean(1),new):
        _,_,index,_=tree.find_nearest(Vector(center));ref=old[index]
        dots.append(float(np.dot(n,ref)/(np.linalg.norm(n)*np.linalg.norm(ref))))
    if min(dots)<=0: raise ValueError('Edited triangle reverses the original surface')
    return min(dots)


def uv_orientation(p,f,uv,q,g,new_uv):
    tree=surface(p,f)
    old_tri=uv[f];new_tri=new_uv[g]
    def areas(t):
        a=t[:,1]-t[:,0];b=t[:,2]-t[:,0]
        return a[:,0]*b[:,1]-a[:,1]*b[:,0]
    old_area=areas(old_tri);new_area=areas(new_tri);checked=0
    for center,value in zip(q[g].mean(1),new_area):
        _,_,index,_=tree.find_nearest(Vector(center));reference=old_area[index]
        # Authored cone caps have constant UVs and hence no tangent direction.
        if abs(reference)>1e-10 and abs(value)>1e-10:
            if reference*value<0:raise ValueError('UV winding mirrors its original surface')
            checked+=1
    return checked


def barycentric(v, a, b, c):
    x=b-a;y=c-a;z=v-a
    xx=np.dot(x,x);xy=np.dot(x,y);yy=np.dot(y,y)
    den=xx*yy-xy*xy
    if abs(den)<1e-25:return np.array([1.,0.,0.])
    s=(yy*np.dot(z,x)-xy*np.dot(z,y))/den
    t=(xx*np.dot(z,y)-xy*np.dot(z,x))/den
    return np.array([1-s-t,s,t])
