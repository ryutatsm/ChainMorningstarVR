"""Closed spherical plaque carrying the user's complete, non-tiling emblem.

The uploaded diamond replaces the previous independent dragon extrusion.  UVs
are one-to-one source-image coordinates; no second outline is laid over it.
Only low-frequency image relief enters the mesh. Fine detail stays in textures.
"""
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

SOURCE_SIZE = 1254
# Pixel coordinates on the outer edge of the supplied diamond, clockwise.
SOURCE_CORNERS = np.array([[626.,10.],[999.,583.],[625.,1202.],[251.,583.]])
SOURCE_CENTER = np.array([625.,606.])
SPHERE_RADIUS = .16
FRONT_RADIUS = .1607
BACK_RADIUS = .147
RELIEF_DEPTH = .0018
HEIGHT = .256
SUBDIVISIONS = 64


def _sampled_disk(corners, center, subdivisions):
    """Conforming four-fan triangulation, including exactly shared fan seams."""
    vertices=[];faces=[];lookup={}
    def index(pixel):
        key=tuple(np.round(pixel,8))
        if key not in lookup:
            lookup[key]=len(vertices);vertices.append(pixel)
        return lookup[key]
    for side in range(4):
        a=corners[side];b=corners[(side+1)%4];indices={}
        for i in range(subdivisions+1):
            for j in range(subdivisions+1-i):
                indices[i,j]=index(center+(a-center)*(i/subdivisions)+(b-center)*(j/subdivisions))
        for i in range(subdivisions):
            for j in range(subdivisions-i):
                faces.append([indices[i,j],indices[i+1,j],indices[i,j+1]])
                if i+j<subdivisions-1:
                    faces.append([indices[i+1,j],indices[i+1,j+1],indices[i,j+1]])
    boundary=[]
    for side in range(4):
        a=corners[side];b=corners[(side+1)%4]
        boundary.extend(index(a+(b-a)*(j/subdivisions)) for j in range(subdivisions))
    return np.asarray(vertices),np.asarray(faces),np.asarray(boundary)


def _normal_surface(vertices, faces, outward=True):
    faces=faces.copy()
    cross=np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]])
    wanted=vertices[faces].mean(axis=1)*(1 if outward else -1)
    flip=(cross*wanted).sum(axis=1)<0
    faces[flip]=faces[flip][:,[0,2,1]]
    cross=np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]])
    normal=np.zeros_like(vertices)
    for column in range(3):np.add.at(normal,faces[:,column],cross)
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-20)
    return normal,faces


def create_relief(texture_path):
    texture_path=Path(texture_path)
    rgb=np.asarray(Image.open(texture_path).convert('RGB'),dtype=np.float64)/255.
    luma=rgb@np.array([.2126,.7152,.0722])
    # Broad metal facets rise at most 1.8 mm; tiny scratches never turn into
    # long spikes. The image remains authoritative for all painted detail.
    height=RELIEF_DEPTH*np.clip((gaussian_filter(luma,3.0,mode='nearest')-.12)/.70,0,1)
    pixel,faces,boundary=_sampled_disk(SOURCE_CORNERS,SOURCE_CENTER,SUBDIVISIONS)
    scale=HEIGHT/(SOURCE_CORNERS[:,1].max()-SOURCE_CORNERS[:,1].min())
    x=(pixel[:,0]-SOURCE_CENTER[0])*scale
    z=(SOURCE_CENTER[1]-pixel[:,1])*scale
    uv=np.column_stack([pixel[:,0]/(SOURCE_SIZE-1),1-pixel[:,1]/(SOURCE_SIZE-1)])
    displacement=map_coordinates(height,[pixel[:,1]/(SOURCE_SIZE-1)*(rgb.shape[0]-1),pixel[:,0]/(SOURCE_SIZE-1)*(rgb.shape[1]-1)],order=1,mode='nearest')
    front_r=FRONT_RADIUS+displacement
    assert np.max(x*x+z*z)<SPHERE_RADIUS**2,'Plaque extends beyond the sphere horizon'
    directions=np.column_stack([x,-np.sqrt(SPHERE_RADIUS**2-x*x-z*z),z])/SPHERE_RADIUS
    # Radial thickness: corresponding front/back vertices share a ray. The
    # hidden backing contracts into the forged core instead of forming a deep
    # vertical skirt at the near-horizon tips.
    front_v=directions*front_r[:,None]
    back_v=directions*BACK_RADIUS
    front_n,front_f=_normal_surface(front_v,faces)
    back_n,back_f=_normal_surface(back_v,faces,False)
    front=dict(v=front_v,n=front_n,uv=uv,f=front_f)
    back=dict(v=back_v,n=back_n,uv=uv,f=back_f)
    side_v=[];side_n=[];side_uv=[];side_f=[]
    for i,a in enumerate(boundary):
        b=boundary[(i+1)%len(boundary)]
        verts=np.array([front_v[a],front_v[b],back_v[b],back_v[a]])
        normal=np.cross(verts[1]-verts[0],verts[2]-verts[0]);normal/=np.linalg.norm(normal)
        # Point away from the diamond interior in its X/Z projection,
        # independently of the shallow image displacement.
        outward=np.array([-(z[b]-z[a]),0,x[b]-x[a]])
        if np.dot(normal,outward)<0:normal=-normal
        off=len(side_v);side_v.extend(verts);side_n.extend([normal]*4)
        side_uv.extend([[i/len(boundary)*4,1],[(i+1)/len(boundary)*4,1],[(i+1)/len(boundary)*4,0],[i/len(boundary)*4,0]])
        fs=np.array([[0,1,2],[0,2,3]])
        cr=np.cross(verts[fs[:,1]]-verts[fs[:,0]],verts[fs[:,2]]-verts[fs[:,0]])
        fs[np.sum(cr*normal,axis=1)<0]=fs[np.sum(cr*normal,axis=1)<0][:,[0,2,1]]
        side_f.extend((fs+off).tolist())
    sides=dict(v=np.asarray(side_v),n=np.asarray(side_n),uv=np.asarray(side_uv),f=np.asarray(side_f))
    metadata=dict(source_texture='エンブレム.png',processed_texture=texture_path.name,
        processed_texture_sha256=hashlib.sha256(texture_path.read_bytes()).hexdigest(),
        source_dimensions_px=[SOURCE_SIZE,SOURCE_SIZE],source_corners_px=SOURCE_CORNERS.tolist(),
        center_pixel=SOURCE_CENTER.tolist(),scale_m_per_pixel=scale,height_m=HEIGHT,
        surface='spherical_radial_image_relief',sphere_radius_m=SPHERE_RADIUS,front_base_radius_m=FRONT_RADIUS,
        back_radius_m=BACK_RADIUS,maximum_image_relief_m=RELIEF_DEPTH,
        sampled_front_radius_range_m=[float(front_r.min()),float(front_r.max())],
        image_height_filter_sigma_px=3.0,edge_subdivisions=SUBDIVISIONS,
        boundary_vertex_indices=boundary.tolist(),front_vertices=len(front_v),front_triangles=len(front_f),
        crest_rotation_rad=float(np.pi/3),
        replaces_previous_contour=True,
        limitation='The full supplied diamond is texture-mapped with shallow image-derived relief; it is not a recovered sculpture or separately extruded dragon.')
    return front,back,sides,metadata
