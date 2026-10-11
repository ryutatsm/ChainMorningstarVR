"""Only the reviewed grip-edge change, checked independently by export and CI.

Keep the original 16-sided exterior rings and their UVs/normals. Drop the
least-deviating middle axial ring, then add two 16-to-8 annuli. The inner
vertices penetrate the unchanged wooden surface by 0.08 mm to prevent gaps.
"""
from pathlib import Path
import numpy as np
from cms_io import load,sha256

POLICY='leather-contact-annuli-v1'
LEATHER='CMS_CMS_ROOT_leather'
WOOD='CMS_CMS_ROOT_wood'
SOURCE_SHA256='d8e8b3b252f283ac1ff33b72b8c3f3c0ac486a60a5deb8b5213caa4124d55ca5'
BODY_TRIANGLES=128
CAP_TRIANGLES=48
INSET_M=.00008

def source():
    path=Path(__file__).parent/'contracts/leather_edge_source.cms'
    if sha256(path.read_bytes())!=SOURCE_SHA256:raise ValueError('Leather edge source hash changed')
    return load(path,require_baseline=False)

def mesh(cms,name):return next(m for m in cms['meshes'] if m['name']==name)

def slice_wood(wood,y):
    p=np.array(wood['vertices'])[:,:3];segments=[]
    for face in wood['faces']:
        t=p[list(face)];points=[]
        for a,b in zip(t,np.roll(t,-1,axis=0)):
            if (a[1]-y)*(b[1]-y)<0:
                v=a+(b-a)*((y-a[1])/(b[1]-a[1]));points.append(v[[0,2]])
        if len(points)==2:segments.append(points)
    if not segments:raise ValueError('Leather end escaped wood')
    return np.array(segments)

def radial_contact(segments,d):
    answers=[]
    for a,b in segments:
        try:r,t=np.linalg.solve(np.column_stack((d,a-b)),a)
        except np.linalg.LinAlgError:continue
        if r>0 and -1e-7<=t<=1+1e-7:answers.append(r)
    if not answers:raise ValueError('No wood contact along leather radius')
    return max(answers)

def build(cms=None):
    cms=cms or source();old=mesh(cms,LEATHER);wood=mesh(cms,WOOD)
    v=np.array(old['vertices']);grid=v[np.lexsort((v[:,6],v[:,7]))].reshape(6,17,8)
    if not np.allclose(grid[:,:,6],np.linspace(0,1,17)[None,:],atol=1e-7):raise ValueError('Wrong source grip grid')
    kept=grid[[0,1,3,4,5]];rows=kept.reshape(-1,8).tolist();faces=[]
    for r in range(4):
        for c in range(16):
            a=r*17+c;b=a+17
            faces.extend(((a,b,a+1),(a+1,b,b+1)))
    contact_errors=[];thickness=[]
    for end,sign in ((0,-1),(4,1)):
        outer=kept[end];y=float(outer[0,1]);segments=slice_wood(wood,y)
        cap=[]
        for row in outer:
            cap.append([*row[:3],0.,float(sign),0.,float(row[6]),float(row[7])])
        inner=[]
        for row in outer[::2]:
            d=row[[0,2]]/np.linalg.norm(row[[0,2]]);r=radial_contact(segments,d)
            point=d*(r-INSET_M);thickness.append(float(np.linalg.norm(row[[0,2]])-r))
            inner.append([point[0],y,point[1],0.,float(sign),0.,float(row[6]),.012 if end==0 else .988])
        base=len(rows);rows+=cap+inner
        for k in range(8):
            a=base+2*k;b=a+1;c=a+2;d=base+17+k;e=d+1
            for tri in ((a,b,d),(b,e,d),(b,c,e)):
                t=np.array(rows)[list(tri),:3]
                if np.cross(t[1]-t[0],t[2]-t[0])[1]*sign<0:tri=tuple(reversed(tri))
                faces.append(tri)
        # Both the vertices and all the inner-edge samples must lie inside the
        # actual triangulated wooden surface, not an idealized circular shaft.
        for a,b in zip(np.array(inner)[:-1,:3],np.array(inner)[1:,:3]):
            for t in np.linspace(0,1,17):
                point=a*(1-t)+b*t;d=point[[0,2]]/np.linalg.norm(point[[0,2]])
                gap=np.linalg.norm(point[[0,2]])-radial_contact(segments,d)
                if gap>1e-7:raise ValueError('Leather inner edge floats above wood')
                contact_errors.append(float(gap))
    return np.array(rows),np.array(faces,dtype=int),dict(
        policy=POLICY,source_cms_sha256=SOURCE_SHA256,body_triangles=BODY_TRIANGLES,
        added_edge_triangles=CAP_TRIANGLES,removed_middle_triangles=32,
        inner_ring_vertices_per_end=8,wood_inset_mm=INSET_M*1000,
        exposed_thickness_mm=[min(thickness)*1000,max(thickness)*1000],
        maximum_inner_edge_gap_mm=max(contact_errors)*1000,
        retained_exterior_vertices_uv_normals=True,other_meshes_unchanged=True)

def validate_rows(rows,faces):
    expected,f,proof=build()
    actual=np.array(rows)[np.array(faces)];wanted=expected[f]
    # Blender stores split custom normals in a quantized mesh representation.
    # Geometry/UV remain strict; permit only the observed <0.005-degree normal
    # roundtrip, never use this tolerance for positions or wood contact.
    if (actual.shape!=wanted.shape or
        not np.allclose(actual[:,:,:3],wanted[:,:,:3],atol=1e-7,rtol=0) or
        not np.allclose(actual[:,:,6:8],wanted[:,:,6:8],atol=1e-7,rtol=0) or
        not np.allclose(actual[:,:,3:6],wanted[:,:,3:6],atol=8e-5,rtol=0)):
        raise ValueError('Leather edge differs from the reviewed contact geometry/UV/normals')
    return proof

def validate_unchanged(edited,original):
    if edited['faces']!=original['faces'] or not np.array_equal(np.array(edited['vertices']),np.array(original['vertices'])):
        raise ValueError('Unrelated mesh changed during leather edge finish: '+edited['name'])

def validate_cms(cms):
    old=source();proof=None
    for m in cms['meshes']:
        original=mesh(old,m['name'])
        if m['name']==LEATHER:proof=validate_rows(m['vertices'],m['faces'])
        else:validate_unchanged(m,original)
    if len(cms['meshes'])!=len(old['meshes']) or proof is None:raise ValueError('Leather edge mesh inventory changed')
    return proof
