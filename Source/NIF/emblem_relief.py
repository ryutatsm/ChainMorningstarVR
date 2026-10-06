"""Extrude the exact reference silhouette without expanding its boundary.

The constrained source triangulation preserves every re-entrant bay.
It is never redrawn, simplified, mirrored or rescaled nonuniformly here.
"""
from pathlib import Path
import json
import numpy as np

def create_relief(asset_path,height_m=.194,front_y=-.1704,back_y=-.1588):
    data=json.loads(Path(asset_path).read_text());poly=data['polygons'][0]
    assert len(data['polygons'])==1 and not poly['holes'],'Unexpected traced topology'
    outline=np.asarray(poly['outer'],dtype=float)
    original=np.asarray(data['mesh2d']['vertices'],dtype=float)
    original_tri=np.asarray(data['mesh2d']['triangles'],dtype=int)
    assert np.array_equal(outline,original),'Contour/mesh index convention changed'
    v2=original.copy();front_tri=original_tri.copy()
    x0,y0,x1,y1=data['bbox'];scale=height_m/(y1-y0);center=np.array([(x0+x1)*.5,(y0+y1)*.5])
    # Preserve source proportions and leave clearance inside the inner diamond.
    clearance=np.max(np.abs(original[:,0]-center[0])/.0501+np.abs(original[:,1]-center[1])/.1063)
    scale=min(scale,.92/clearance);height_m=scale*(y1-y0)
    yy=np.full(len(original),front_y)
    front_v=np.column_stack([(v2[:,0]-center[0])*scale,yy,(center[1]-v2[:,1])*scale])
    front_tri=front_tri[:,[0,2,1]]
    front_n=np.tile([0,-1,0],(len(original),1))
    # Clean existing metal atlas patch, source V-up. The logo remains a real
    # opaque relief mesh: there is no decal/alpha image hiding bad geometry.
    def uv_from_px(p):
        return np.column_stack([.48828125+(p[:,0]-x0)/(x1-x0)*.0625,.552734375+(y1-p[:,1])/(y1-y0)*.0625])
    front=dict(v=front_v,n=front_n,uv=uv_from_px(v2),f=front_tri)
    back_v=np.column_stack([(original[:,0]-center[0])*scale,np.full(len(original),back_y),(center[1]-original[:,1])*scale])
    back_tri=original_tri.copy();back_n=np.tile([0,1,0],(len(original),1))
    back=dict(v=back_v,n=back_n,uv=uv_from_px(original),f=back_tri)
    # Side walls use the exact original perimeter, including every concave bay.
    side_v=[];side_n=[];side_uv=[];side_f=[]
    for i in range(len(original)):
        j=(i+1)%len(original);a=front_v[i];b=front_v[j];c=back_v[j];d=back_v[i]
        normal=np.cross(b-a,c-a);normal/=max(np.linalg.norm(normal),1e-15)
        off=len(side_v);side_v.extend([a,b,c,d]);side_n.extend([normal]*4)
        side_uv.extend([[.51,.57],[.54,.57],[.54,.59],[.51,.59]])
        side_f.extend([[off,off+1,off+2],[off,off+2,off+3]])
    sides=dict(v=np.asarray(side_v),n=np.asarray(side_n),uv=np.asarray(side_uv),f=np.asarray(side_f))
    metadata=dict(source=data['source'],source_bbox=data['bbox'],source_contour_points=len(original),scale_m_per_pixel=scale,center_pixel=center.tolist(),height_m=height_m,front_y=front_y,back_y=back_y,bevel_depth_m=0.0,diamond_clearance_ratio=.92,crest_rotation_rad=float(np.pi/4),source_fidelity=data.get('fidelity',{}),front_vertices=len(front_v),front_triangles=len(front_tri))
    return front,back,sides,metadata
