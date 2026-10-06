"""Trace a black-background emblem reference into reusable contour geometry.

Only the largest foreground silhouette is retained. Enclosed dark islands in
this particular reference are hammered-metal shading, not structural holes;
the intentional negative spaces are open, re-entrant bays of the outer ring.
The committed JSON is the build input; the original JPEG is not needed by CI.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def area(points):
    p=np.asarray(points)
    return float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))*.5)


def trace_mask(mask):
    """Marching squares, with four-connected foreground in saddle cells."""
    padded=np.pad(mask.astype(np.uint8),1)
    cases=padded[:-1,:-1]+2*padded[:-1,1:]+4*padded[1:,1:]+8*padded[1:,:-1]
    # Edge names: top, right, bottom, left. Saddles retain disconnected diagonals.
    pairs={1:[(0,3)],2:[(0,1)],3:[(3,1)],4:[(1,2)],5:[(0,3),(1,2)],
           6:[(0,2)],7:[(3,2)],8:[(2,3)],9:[(0,2)],10:[(0,1),(2,3)],
           11:[(1,2)],12:[(1,3)],13:[(0,1)],14:[(0,3)]}
    graph={}
    for y,x in np.argwhere((cases>0)&(cases<15)):
        corners=[(2*x+1,2*y),(2*x+2,2*y+1),(2*x+1,2*y+2),(2*x,2*y+1)]
        for a,b in pairs[int(cases[y,x])]:
            a,b=corners[a],corners[b]
            graph.setdefault(a,[]).append(b);graph.setdefault(b,[]).append(a)
    assert all(len(v)==2 for v in graph.values())
    unseen=set(graph);rings=[]
    while unseen:
        start=min(unseen);point=start;last=None;ring=[]
        while True:
            ring.append(point);unseen.discard(point)
            choices=graph[point];nxt=choices[0] if choices[0]!=last else choices[1]
            last,point=point,nxt
            if point==start:break
        rings.append(np.asarray(ring,dtype=float)/2-1)
    return sorted(rings,key=lambda p:abs(area(p)),reverse=True)


def rdp(points,tolerance):
    if len(points)<3:return points
    a,b=points[0],points[-1];d=b-a;den=float(d@d)
    if den:
        t=np.clip(((points-a)@d)/den,0,1)
        distance=np.linalg.norm(points-(a+t[:,None]*d),axis=1)
    else:distance=np.linalg.norm(points-a,axis=1)
    k=int(np.argmax(distance))
    if distance[k]<=tolerance:return points[[0,-1]]
    return np.vstack([rdp(points[:k+1],tolerance)[:-1],rdp(points[k:],tolerance)])


def simplify_ring(points,tolerance):
    first=int(np.lexsort((points[:,1],points[:,0]))[0])
    p=np.roll(points,-first,axis=0)
    split=int(np.argmax(np.sum((p-p[0])**2,axis=1)))
    result=np.vstack([rdp(p[:split+1],tolerance)[:-1],rdp(np.vstack([p[split:],p[:1]]),tolerance)[:-1]])
    if area(result)<0:result=result[::-1]
    return result


def inside_points(x,y,polygon):
    """Ray-crossing rasterizer independent of marching squares and triangulator."""
    inside=np.zeros(np.broadcast_shapes(np.shape(x),np.shape(y)),bool)
    for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
        if a[1]==b[1]:continue
        crossing=((a[1]>y)!=(b[1]>y)) & (x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
        inside ^= crossing
    return inside


def earclip(polygon):
    """Triangulate a simple ring exactly; no unconstrained-Delaunay gaps."""
    p=np.asarray(polygon,dtype=float)
    assert area(p)>0
    remaining=list(range(len(p)));triangles=[]
    while len(remaining)>3:
        found=False
        for k,b in enumerate(remaining):
            a,c=remaining[k-1],remaining[(k+1)%len(remaining)]
            av,bv,cv=p[[a,b,c]]
            cross=lambda u,v:u[...,0]*v[...,1]-u[...,1]*v[...,0]
            if cross(bv-av,cv-bv)<=1e-10:continue
            other=np.asarray([i for i in remaining if i not in (a,b,c)],int)
            pts=p[other]
            lo=np.minimum(np.minimum(av,bv),cv);hi=np.maximum(np.maximum(av,bv),cv)
            pts=pts[np.all((pts>=lo-1e-10)&(pts<=hi+1e-10),axis=1)]
            contained=(cross(bv-av,pts-av)>=-1e-10)&(cross(cv-bv,pts-bv)>=-1e-10)&(cross(av-cv,pts-cv)>=-1e-10)
            if np.any(contained):continue
            triangles.append([a,b,c]);del remaining[k];found=True;break
        if not found:raise ValueError('Non-simple or degenerate polygon; decrease simplification tolerance')
    triangles.append(remaining)
    return triangles


def svg_preview(polygon,width,height,path):
    points=' '.join(f'{x:g},{y:g}' for x,y in polygon)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#202124"/><polygon points="{points}" fill="#bfc5ca" stroke="#e8eef2" stroke-width="0.6"/></svg>\n')


def extract(source,out,tolerance=.65):
    image=Image.open(source).convert('RGB');rgb=np.asarray(image)
    gray=np.asarray(image.convert('L'))
    threshold=10
    binary=gray>=threshold
    labels,n=ndimage.label(binary)
    counts=np.bincount(labels.ravel());counts[0]=0
    foreground=labels==counts.argmax()
    solid=ndimage.binary_fill_holes(foreground)
    rings=trace_mask(solid)
    assert len(rings)==1,'Expected one connected silhouette with no closed through-hole'
    polygon=simplify_ring(rings[0],tolerance)
    triangles=earclip(polygon)
    y,x=np.mgrid[:image.height,:image.width]
    raster=inside_points(x,y,polygon)
    union=np.count_nonzero(raster|solid);intersection=np.count_nonzero(raster&solid)
    iou=intersection/union
    boundary=solid^ndimage.binary_erosion(solid)
    simplified_boundary=raster^ndimage.binary_erosion(raster)
    distance_to_source=ndimage.distance_transform_edt(~boundary)
    distance_to_result=ndimage.distance_transform_edt(~simplified_boundary)
    hausdorff=max(float(distance_to_source[simplified_boundary].max()),float(distance_to_result[boundary].max()))
    p=np.asarray(polygon);t=np.asarray(triangles)
    a=p[t[:,1]]-p[t[:,0]];b=p[t[:,2]]-p[t[:,0]]
    triangle_area=(a[:,0]*b[:,1]-a[:,1]*b[:,0])*.5
    assert (triangle_area>0).all()
    assert abs(float(triangle_area.sum())-area(p))<1e-6
    assert iou>=.985 and hausdorff<=2.0,(iou,hausdorff)
    # Feature bounds locate diagnostic narrow tips, curls and asymmetric tail;
    # all positions come from the single original outline, never a redesign.
    result=dict(schema_version=1,
                source=dict(filename=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),width=image.width,height=image.height),
                coordinate_system='image pixel centers; +x right, +y down; outer ring has positive signed area',
                bbox=[float(p[:,0].min()),float(p[:,1].min()),float(p[:,0].max()),float(p[:,1].max())],
                polygons=[dict(outer=p.tolist(),holes=[])],
                mesh2d=dict(vertices=p.tolist(),triangles=triangles),
                extraction=dict(grayscale_threshold=threshold,foreground_connectivity=4,
                    retain='largest connected foreground',fill_enclosed_dark_surface_marks=True,
                    note='Intentional open wing/neck/tail negative spaces remain in the re-entrant outer contour; enclosed dark pixels inside metal faces are source shading.',
                    raw_boundary_vertices=len(rings[0]),simplified_vertices=len(p),simplification_tolerance_pixels=tolerance),
                fidelity=dict(source_silhouette_pixels=int(solid.sum()),traced_silhouette_pixels=int(raster.sum()),
                    raster_intersection_over_union=iou,boundary_hausdorff_pixels=hausdorff,
                    triangle_area_sum=float(triangle_area.sum()),polygon_area=area(p),
                    relative_triangle_area_error=abs(float(triangle_area.sum())-area(p))/area(p),
                    assessment='Contour accuracy against extracted silhouette; relief depth and internal metal facets are authored separately.'))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    svg_preview(p,image.width,image.height,out.with_suffix('.svg'))
    print(json.dumps({k:v for k,v in result.items() if k not in ['polygons','mesh2d']},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--tolerance',type=float,default=.65);args=parser.parse_args()
    extract(args.source,args.out,args.tolerance)
