"""Deterministic reference-based asset geometry; no Blender or prior weapon asset.

Writes an interchange file consumed by export_reference_nif.cpp and a glTF 2.0
binary with the SAME vertices, normals, UVs and hierarchy for inspection.
Distances are meters here; the NIF exporter converts only visual vertices/node
translations to Skyrim units. Havok hull vertices stay in meters.
"""
from __future__ import annotations
import json, math, struct, argparse, io
from pathlib import Path
import numpy as np
from PIL import Image
from emblem_relief import create_relief

SU = 69.99125
NODES = []
MESHES = {}
COLLISION = []
FEATURES = []
EMBLEM = {}
MATERIALS = ['metal', 'wood', 'leather', 'darksteel', 'edge', 'cord', 'bronze', 'spike', 'chain', 'ring', 'emblem']
TEXTURE_BASES = ['metal', 'wood', 'leather', 'cord', 'spike', 'chain', 'ring', 'emblem']

def unit(v):
    v=np.asarray(v,dtype=float)
    return v/max(np.linalg.norm(v),1e-10)

def node(name,parent,translation=(0,0,0),rotation=None):
    NODES.append(dict(name=name,parent=parent,t=list(translation),r=np.eye(3).tolist() if rotation is None else rotation))
    return len(NODES)-1

class Mesh:
    def __init__(self,parent,material):
        self.parent,self.material=parent,material
        self.v=[]; self.n=[]; self.uv=[]; self.f=[]
    def add(self,v,n,uv,f):
        v=np.asarray(v);n=np.asarray(n);f=np.asarray(f,dtype=int)
        face_normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
        valid=np.linalg.norm(face_normal,axis=1)>1e-12
        f=f[valid];face_normal=face_normal[valid]
        inward=np.sum(face_normal*n[f].mean(1),axis=1)<0
        f[inward]=f[inward][:,[0,2,1]]
        off=len(self.v)
        self.v.extend(np.asarray(v).tolist()); self.n.extend(np.asarray(n).tolist()); self.uv.extend(np.asarray(uv).tolist())
        self.f.extend([[a+off,b+off,c+off] for a,b,c in f])

def mesh(parent,material):
    k=(parent,material)
    if k not in MESHES: MESHES[k]=Mesh(parent,material)
    return MESHES[k]

def frame(d):
    d=unit(d); ref=[0,0,1] if abs(d[2])<.85 else [0,1,0]
    u=unit(np.cross(ref,d)); return d,u,np.cross(d,u)

def lathe(parent,mat,profile,axis=(0,1,0),origin=(0,0,0),segs=48,texture_repeat=1):
    d,u,w=frame(axis); v=[]; n=[]; uv=[]; f=[]; o=np.asarray(origin)
    for j,(z,r) in enumerate(profile):
        prv=profile[max(j-1,0)]; nxt=profile[min(j+1,len(profile)-1)]
        slope=(nxt[1]-prv[1])/max(nxt[0]-prv[0],1e-8)
        for i in range(segs+1):
            a=2*math.pi*i/segs; radial=math.cos(a)*u+math.sin(a)*w
            v.append(o+d*z+radial*r); n.append(unit(radial-d*slope)); uv.append([i/segs*texture_repeat,j/(len(profile)-1)])
    for j in range(len(profile)-1):
        for i in range(segs):
            a=j*(segs+1)+i; b=a+segs+1
            f.extend([[a,a+1,b],[a+1,b+1,b]])
    mesh(parent,mat).add(v,n,uv,f)

def tube(parent,mat,points,radius,sides=8,closed=False):
    p=np.asarray(points); count=len(p); v=[]; n=[]; uv=[]; f=[]
    prior_u=None
    for i,q in enumerate(p):
        d=p[(i+1)%count]-p[(i-1)%count] if closed else p[min(i+1,count-1)]-p[max(0,i-1)]
        d,u,w=frame(d)
        if prior_u is not None:
            projected=prior_u-d*np.dot(prior_u,d)
            if np.linalg.norm(projected)>1e-5:u=unit(projected);w=np.cross(d,u)
        prior_u=u
        for j in range(sides+1):
            a=j/sides*2*math.pi; norm=math.cos(a)*u+math.sin(a)*w
            v.append(q+radius*norm); n.append(norm); uv.append([j/sides,i/count*3])
    if closed:
        # Duplicate the exact first geometric ring at the terminal V. Reusing
        # its V=0 vertices would drag almost three texture repeats backwards
        # over the final link segment and smear the supplied chain material.
        v.extend(v[:sides+1]);n.extend(n[:sides+1]);uv.extend([[j/sides,3.] for j in range(sides+1)])
    for i in range(count if closed else count-1):
        k=i+1
        for j in range(sides):
            a=i*(sides+1)+j; b=k*(sides+1)+j
            f.extend([[a,a+1,b],[a+1,b+1,b]])
    mesh(parent,mat).add(v,n,uv,f)

def ring(parent,mat,radius,tube_radius,center=(0,0,0),axis=(0,1,0),stretch=1,segs=48):
    _,u,w=frame(axis); p=[]; o=np.asarray(center)
    for a in np.linspace(0,2*math.pi,segs,endpoint=False): p.append(o+radius*(math.cos(a)*u+math.sin(a)*w*stretch))
    tube(parent,mat,p,tube_radius,10,True)

def sphere(parent,mat,radius=.16,center=(0,0,0),segs=48,rings=24):
    v=[];n=[];uv=[];f=[];o=np.asarray(center)
    for j in range(rings+1):
        th=j/rings*math.pi
        for i in range(segs+1):
            ph=i/segs*2*math.pi; q=np.array([math.sin(th)*math.cos(ph),math.sin(th)*math.sin(ph),math.cos(th)])
            # Mild forged facets; visual core stays within the physical sphere.
            rr=radius*(1-.004*(math.sin(ph*7+th*11)**2))
            v.append(o+q*rr);n.append(q);uv.append([i/segs*2,j/rings])
    for j in range(rings):
        for i in range(segs):
            a=j*(segs+1)+i;b=a+segs+1
            if j: f.append([a,b,a+1])
            if j<rings-1: f.append([a+1,b,b+1])
    mesh(parent,mat).add(v,n,uv,f)

def sculpt_grid(parent,mat,positions,uvs,outward,feature=None):
    """Emit a sampled sculpt surface with normals derived from real geometry."""
    v=np.asarray(positions); nr,nc,_=v.shape;flat=v.reshape(-1,3);f=[]
    for j in range(nr-1):
        for i in range(nc-1):
            a=j*nc+i;b=a+nc;f.extend([[a,a+1,b],[a+1,b+1,b]])
    f=np.asarray(f);ref=np.asarray(outward).reshape(-1,3)
    face=np.cross(flat[f[:,1]]-flat[f[:,0]],flat[f[:,2]]-flat[f[:,0]])
    inward=np.sum(face*ref[f].mean(1),axis=1)<0;f[inward]=f[inward][:,[0,2,1]]
    face=np.cross(flat[f[:,1]]-flat[f[:,0]],flat[f[:,2]]-flat[f[:,0]])
    normals=np.zeros_like(flat)
    for i in range(3):np.add.at(normals,f[:,i],face)
    normals=normals.reshape(nr,nc,3)
    for j in range(nr):
        if np.max(np.linalg.norm(v[j]-v[j,0],axis=1))<1e-12:
            # All UV-longitude copies of a spherical pole share one normal.
            # Per-wedge normals are undefined at this collapsed row.
            normals[j]=normals[j].sum(axis=0)
        else:
            combined=normals[j,0]+normals[j,-1];normals[j,0]=combined;normals[j,-1]=combined
    normals=normals.reshape(-1,3);length=np.linalg.norm(normals,axis=1)
    tiny=length<1e-10;normals[tiny]=ref[tiny];length=np.linalg.norm(normals,axis=1)
    normals/=np.maximum(length[:,None],1e-10)
    obj=mesh(parent,mat);start=len(obj.v);obj.add(flat,normals,np.asarray(uvs).reshape(-1,2),f)
    if feature:FEATURES.append(dict(name=feature,parent=parent,material=mat,vertex_start=start,vertex_count=len(flat)))

def wrapped_angle(a):return (a+math.pi)%(2*math.pi)-math.pi

def wood_radius(a,y):
    # 27 mm near the chain, 39 mm toward the hand: taper is now unambiguous.
    r=.0395-(y+.16)/.56*.0135
    r+=.00085*math.sin(7*a+.35*math.sin(y*19))+.00045*math.sin(15*a+y*7)
    # Deep split grain is modelled as narrow longitudinal valleys, not painted.
    for angle,shift,depth,width in [(.4,.13,.0013,.055),(1.45,.20,.0018,.045),(2.3,-.15,.0012,.065),(3.8,.11,.0015,.05),(5.2,.22,.001,.07)]:
        da=wrapped_angle(a-angle-shift*math.sin(y*8+angle))
        r-=depth*math.exp(-(da/width)**2)*(.65+.35*math.sin(y*17+angle)**2)
    for aa,yy,depth in [(math.pi/2,.225,.0036),(-.55,.30,.0026)]:
        dx=wrapped_angle(a-aa)/.20;dy=(y-yy)/.022;q=dx*dx+dy*dy
        r-=depth*math.exp(-q*1.5)
        r+=.0026*math.exp(-((math.sqrt(q)-1.1)/.42)**2)
    return r

def leather_radius(a,y):
    t=(y+.115)/.255;r=.0426-.0076*t
    lace_t=(y+.108)/.237
    # Pressure under crossing laces; slack old hide swells in each diamond.
    distances=[wrapped_angle(a-sign*(lace_t*2*math.pi*4.6)-.4) for sign in [-1,1]]
    compressed=sum(math.exp(-(da/.11)**2) for da in distances)
    r+=.0015*(1-min(1,compressed))-.0012*compressed
    r+=.00065*math.sin(a*5+y*34)+.00045*math.sin(a*11-y*61)
    r+=.00048*math.sin(y*320+.85*math.sin(a*4))*(.35+.65*math.sin(a*3+y*55)**2)
    # Rolled, uneven leather edges at top and bottom.
    r+=.0014*math.exp(-((y-.135-.0008*math.sin(a*6))/.004)**2)
    r+=.0012*math.exp(-((y+.109+.0007*math.sin(a*5))/.004)**2)
    return r

def sculpt_handle(root):
    for material,ys,nangular,radfn in [('wood',np.linspace(-.159,.399,75),72,wood_radius),('leather',np.linspace(-.115,.14,91),88,leather_radius)]:
        v=[];uv=[];n=[]
        for y in ys:
            row=[];ur=[];nr=[]
            for a in np.linspace(0,2*math.pi,nangular+1):
                r=radfn(a,y);row.append([r*math.cos(a),y,r*math.sin(a)]);nr.append([math.cos(a),0,math.sin(a)])
                ur.append([a/(2*math.pi),(y+.16)/.56 if material=='wood' else (y+.115)/.255])
            v.append(row);uv.append(ur);n.append(nr)
        sculpt_grid(root,material,v,uv,n,'rough_wood' if material=='wood' else 'compressed_leather')
    # Flat, weathered leather lacing. Cord follows depressed hide, not a cylinder.
    for sign in [-1,1]:
        pts=[]
        for t in np.linspace(0,1,321):
            a=sign*(t*2*math.pi*4.6)+.4;y=-.108+t*.237;r=leather_radius(a,y)+.00145
            pts.append([r*math.cos(a),y,r*math.sin(a)])
        tube(root,'cord',pts,.00165,7)

# Deterministic hammer locations covering every side of the ball.
_rng=np.random.default_rng(1744)
_HAMMERS=[]
for _ in range(105):
    d=unit(_rng.normal(size=3));_HAMMERS.append((d,_rng.uniform(.055,.17),_rng.uniform(.0009,.0045)))

def core_points():
    points=[]
    for z in [-1,-.923879533,-.75,-.382683432,0,.382683432,.75,.923879533,1]:
        rad=math.sqrt(max(0,1-z*z))
        for a in np.linspace(0,2*math.pi,24,endpoint=False):points.append([.16*rad*math.cos(a),.16*rad*math.sin(a),.16*z])
    return np.unique(np.round(points,9),axis=0)

def forged_ball(head):
    from scipy.spatial import ConvexHull
    planes=ConvexHull(core_points()).equations;v=[];uv=[];n=[]
    for latitude,th in enumerate(np.linspace(0,math.pi,41)):
        vr=[];ur=[];nr=[]
        is_pole=latitude in (0,40)
        for ph in np.linspace(0,2*math.pi,81):
            # Canonical pole vectors avoid sin(pi) residue and signed tiny XY.
            q=np.array([0.,0.,1. if latitude==0 else -1.]) if is_pole else np.array([math.sin(th)*math.cos(ph),math.sin(th)*math.sin(ph),math.cos(th)])
            den=planes[:,:3]@q;inside=den>1e-8;r=min(.16,float(np.min(-planes[inside,3]/den[inside])))
            dent=0
            for direction,width,depth in _HAMMERS:
                dist2=max(0,2*(1-float(np.dot(q,direction))))
                dent+=depth*math.exp(-dist2/(width*width))
            # Broad forged depressions plus nonperiodic coarse undulations.
            # Longitude is singular at a pole. Dampen its radial contribution
            # smoothly to zero there; every pole UV copy has one exact radius.
            longitude_weight=0. if is_pole else math.sin(th)**2
            dent+=.00055*(1+longitude_weight*math.sin(ph*9+th*7)*math.sin(ph*3-th*13))
            rr=max(.148,r-dent);vr.append(q*rr);nr.append(q);ur.append([ph/(2*math.pi),th/math.pi])
        v.append(vr);uv.append(ur);n.append(nr)
    sculpt_grid(head,'metal',v,uv,n,'hammered_iron_core')

def battered_spike(head,d,index):
    # Visual cone stays INSIDE the existing convex damage hull. Tips are visibly
    # worn flat; facets and local dents change actual geometry and its normals.
    d,u,w=frame(d);v=[];uv=[];n=[]
    top=.2375-.0011*(index%3);segs=24
    from scipy.spatial import ConvexHull
    core_planes=ConvexHull(core_points()).equations
    # Base penetrates the core so forging dents never expose detached spikes.
    for z in np.r_[.134,.140,.145,.150,np.linspace(.154,top,14)]:
        vr=[];ur=[];nr=[];t=(z-.154)/(.24-.154)
        for a in np.linspace(0,2*math.pi,segs+1):
            polygon=math.cos(math.pi/12)/math.cos((a%(math.pi/6))-math.pi/12)
            r=.046*(1-t)*polygon
            if z<.154:
                radial=math.cos(a)*u+math.sin(a)*w
                den=core_planes[:,:3]@radial;positive=den>1e-8
                allowed=np.min(-(core_planes[:,:3]@(d*z)+core_planes[:,3])[positive]/den[positive])
                r=min(.0415,float(allowed)-.00015)
            dent=.0005*(.6+.4*math.sin(a*5+index+z*90)**2)
            dent+=.0014*math.exp(-(wrapped_angle(a-(index*.79))/.30)**2)*math.exp(-((z-(.177+.005*(index%4)))/.014)**2)
            r=max(.0007,r-dent)
            radial=math.cos(a)*u+math.sin(a)*w;vr.append(d*z+radial*r);nr.append(unit(radial+d*.52));ur.append([a/(2*math.pi),max(0.,min(1.,(z-.134)/(top-.134)))])
        v.append(vr);uv.append(ur);n.append(nr)
    sculpt_grid(head,'spike',v,uv,n,f'battered_spike_{index:02d}')
    # Close each flattened tip with an actual cap so it isn't a hollow cone.
    p=np.asarray(v[-1]);center=d*top;verts=np.vstack([center,p]);norm=np.tile(d,(len(verts),1));f=[[0,j+1,j+2] for j in range(segs)]
    mesh(head,'spike').add(verts,norm,[[.5,1.]]*len(verts),f)
    FEATURES[-1]['vertex_count']+=len(verts)

def polygon_triangles(outline):
    p=np.asarray(outline); remaining=list(range(len(p))); result=[]
    def cross(a,b,c):
        u=b-a;v=c-a;return u[0]*v[1]-u[1]*v[0]
    while len(remaining)>3:
        found=False
        for k,i in enumerate(remaining):
            a,b,c=remaining[k-1],i,remaining[(k+1)%len(remaining)]
            if cross(p[a],p[b],p[c])<=1e-12:continue
            blocked=False
            for j in remaining:
                if j in [a,b,c]:continue
                if min(cross(p[a],p[b],p[j]),cross(p[b],p[c],p[j]),cross(p[c],p[a],p[j]))>=-1e-12:
                    blocked=True;break
            if not blocked:
                result.append([a,b,c]);remaining.pop(k);found=True;break
        if not found:raise ValueError('Non-simple ornament polygon')
    result.append(remaining);return result

def plate(parent,mat,outline,y_front,y_back):
    # Ear clipping handles concave dragon relief without triangles crossing gaps.
    if sum(outline[i][0]*outline[(i+1)%len(outline)][1]-outline[i][1]*outline[(i+1)%len(outline)][0] for i in range(len(outline)))<0:outline=list(reversed(outline))
    triangles=polygon_triangles(outline)
    p=[np.array([x,y_front,z]) for x,z in outline]; v=[];n=[];uv=[];f=[]
    for side,y,normal in [(0,y_front,[0,-1,0]),(1,y_back,[0,1,0])]:
        off=len(v)
        for x,z in outline: v.append([x,y,z]);n.append(normal);uv.append([x*3+.5,z*3+.5])
        for a,b,c in triangles:f.append([off+a,off+b,off+c] if side==0 else [off+a,off+c,off+b])
    for i in range(len(p)):
        a=p[i]; b=p[(i+1)%len(p)]; norm=-unit(np.cross(b-a,[0,y_back-y_front,0]));off=len(v)
        v.extend([a,b,[b[0],y_back,b[2]],[a[0],y_back,a[2]]]);n.extend([norm]*4);uv.extend([[0,0],[1,0],[1,1],[0,1]]);f.extend([[off,off+2,off+1],[off,off+3,off+2]])
    mesh(parent,mat).add(v,n,uv,f)

def rune_band(parent,axis_origin,axis=(0,1,0),radius=.047,length=.036,segments=8):
    # Raised angular knotwork around full circumference, visible from every side.
    d,u,w=frame(axis);o=np.asarray(axis_origin)
    for i in range(segments):
        ang=i*2*math.pi/segments
        path=[]
        for da,z in [(-.22,-.35),(0,.4),(.22,-.35),(0,-.1),(-.22,-.35)]:
            a=ang+da; path.append(o+(math.cos(a)*u+math.sin(a)*w)*radius+d*z*length)
        tube(parent,'edge',path,.0013,5)
        path=[]
        for da,z in [(-.23,.38),(-.23,-.38),(.23,-.38),(.23,.38)]:
            a=ang+da;path.append(o+(math.cos(a)*u+math.sin(a)*w)*(radius-.0005)+d*z*length)
        tube(parent,'darksteel',path,.0011,5)

def build(texture_dir):
    root=node('CMS_ROOT',-1)
    anchor=node('CMS_ChainAnchor',root,(0,.4,0),[[1,0,0],[0,0,1],[0,-1,0]])
    links=[]
    for i in range(14):
        a=(i%2)*math.pi/2;rot=[[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]]
        links.append(node(f'CMS_LinkNode_{i:02d}',anchor,(0,0,.035+i*.84/13),rot))
    head=node('CMS_HeadNode',anchor,(0,0,1.065))
    sculpt_handle(root)
    # Ferrules follow the taper: broad pommel/hand end, narrow chain end.
    for y,r,L in [(-.145,.0485,.044),(.3725,.0365,.055)]:
        profile=[(y-L/2,.031),(y-L/2+.003,r-.005),(y-L/2+.007,r),(y+L/2-.007,r),(y+L/2-.003,r-.004),(y+L/2,.031)]
        lathe(root,'ring',profile)
        for a in [y-L/2+.006,y+L/2-.006]:ring(root,'edge',r,.0025,(0,a,0))
    # Reference has a distinct free pommel ring, never a spherical pommel.
    lathe(root,'metal',[(-.181,.014),(-.178,.022),(-.165,.024),(-.156,.020)])
    ring(root,'bronze',.052,.0085,(0,-.226,0),axis=(0,0,1),segs=64)
    ring(root,'chain',.025,.009,(0,.405,0),axis=(1,0,0),stretch=1.22)
    for i,ln in enumerate(links):
        # Runtime writes alternating roll onto this node, so mesh stays XZ.
        u=np.array([1,0,0]);w=np.array([0,0,1])
        pts=[]
        for t in np.linspace(0,2*math.pi,40,endpoint=False):
            pts.append(u*(.0369*math.cos(t))+w*(.0603*math.sin(t)))
        tube(ln,'chain',pts,.0105,10,True)
    forged_ball(head)
    dirs=[]
    for i in range(8): dirs.append([math.cos(i*math.pi/4+math.pi/8),0,math.sin(i*math.pi/4+math.pi/8)])
    r=math.sqrt(1-.64**2)
    for y in [-.64,.64]:
        for i in range(3):dirs.append([r*math.cos(i*2*math.pi/3),y,r*math.sin(i*2*math.pi/3)])
    # Collar at each spike base creates riveted socket silhouette.
    for index,d in enumerate(dirs):
        battered_spike(head,d,index)
    # Head chain socket finishes at z=-.170, connecting to the last oval link.
    lathe(head,'ring',[(-.202,.023),(-.198,.035),(-.167,.035),(-.154,.028)],axis=(0,0,1))
    ring(head,'chain',.029,.008,(0,0,-.212),axis=(0,1,0),stretch=1.13)
    # The supplied complete emblem replaces the previous independent dragon
    # and frame, preventing two incompatible silhouettes from overlapping.
    crest_starts={k:len(m.v) for k,m in MESHES.items() if k[0]==head}
    front,back,sides,info=create_relief(texture_dir/'cms_emblem_d.png')
    parts=[]
    for name,material,part in [('front','emblem',front),('back','metal',back),('sides','metal',sides)]:
        target=mesh(head,material);vstart=len(target.v);fstart=len(target.f)
        target.add(part['v'],part['n'],part['uv'],part['f'])
        parts.append(dict(name=name,parent=head,material=material,vertex_start=vstart,vertex_count=len(target.v)-vstart,face_start=fstart,face_count=len(target.f)-fstart))
    EMBLEM.update(info,parts=parts)
    # The reference emblem stands almost upright while the weapon lies diagonally.
    angle=info['crest_rotation_rad'];rot=np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]])
    for k,m in MESHES.items():
        if k[0]==head:
            start=crest_starts.get(k,0)
            if start<len(m.v):
                m.v[start:]=(np.asarray(m.v[start:])@rot.T).tolist();m.n[start:]=(np.asarray(m.n[start:])@rot.T).tolist()
    # Independent low-poly convex collision hulls; all planes generated by scipy
    # in a separate pass, never derived from a decorative surface normal.
    from scipy.spatial import ConvexHull
    points=core_points()
    def hull(points,margin):
        points=np.unique(np.round(points,9),axis=0);h=ConvexHull(points)
        # Qhull triangulates coplanar quads; retain one exact plane per face.
        _,plane_indices=np.unique(np.round(h.equations,6),axis=0,return_index=True)
        COLLISION.append(dict(v=points[h.vertices].tolist(),planes=h.equations[np.sort(plane_indices)].tolist(),margin=margin))
    hull(points,.003)
    for d in dirs:
        d,u,w=frame(d);points=[d*.24]
        for a in np.linspace(0,2*math.pi,12,endpoint=False): points.append(d*.154+.046*(math.cos(a)*u+math.sin(a)*w))
        hull(points,.002)
    return dirs

def world_transform(i):
    n=NODES[i];r=np.asarray(n['r']);t=np.asarray(n['t'])
    if n['parent']<0:return r,t
    pr,pt=world_transform(n['parent']);return pr@r,pr@t+pt

def glb(out,texture_dir):
    chunks=bytearray();views=[];accessors=[]
    def raw(data):
        while len(chunks)%4:chunks.append(0)
        off=len(chunks);chunks.extend(data);views.append({'buffer':0,'byteOffset':off,'byteLength':len(data)});return len(views)-1
    def acc(a,typ,ctype):
        a=np.asarray(a,dtype='<f4' if ctype==5126 else '<u2'); view=raw(a.tobytes())
        obj=dict(bufferView=view,componentType=ctype,count=len(a),type=typ)
        if typ=='VEC3':obj.update(min=a.min(0).tolist(),max=a.max(0).tolist())
        accessors.append(obj);return len(accessors)-1
    images=[];textures=[];slots={}
    for base in TEXTURE_BASES:
        for kind in ['d','n']:
            # glTF samples image rows in UV-V direction. Flipping the image lets
            # source UV stay V-up; tangent normal green remains unchanged.
            im=Image.open(texture_dir/f'cms_{base}_{kind}.png').convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if kind=='n':im=im.convert('RGB')
            data=io.BytesIO();im.save(data,format='PNG')
            images.append(dict(bufferView=raw(data.getvalue()),mimeType='image/png'))
            textures.append(dict(source=len(images)-1,sampler=0));slots[(base,kind)]=len(textures)-1
    mats=[]
    for name in MATERIALS:
        base=name if name in TEXTURE_BASES else 'metal'
        factor={'darksteel':[.31,.33,.35,1],'edge':[1,1,1,1],'cord':[1,1,1,1],'bronze':[1,.76,.44,1]}.get(name,[1,1,1,1])
        mats.append(dict(name=name,pbrMetallicRoughness=dict(baseColorTexture={'index':slots[(base,'d')]},baseColorFactor=factor,metallicFactor=0 if name in ['wood','leather','cord'] else .85,roughnessFactor=.48 if name not in ['wood','leather','cord'] else .78),normalTexture=dict(index=slots[(base,'n')],scale=1)))
    nodes=[]
    for n in NODES:
        r=np.asarray(n['r']);mat=np.eye(4);mat[:3,:3]=r;mat[:3,3]=n['t']
        nodes.append(dict(name=n['name'],matrix=mat.T.flatten().tolist(),children=[]))
    for i,n in enumerate(NODES):
        if n['parent']>=0:nodes[n['parent']]['children'].append(i)
    meshes=[]
    for (par,mat),m in MESHES.items():
        p=dict(attributes=dict(POSITION=acc(m.v,'VEC3',5126),NORMAL=acc(m.n,'VEC3',5126),TEXCOORD_0=acc(m.uv,'VEC2',5126)),indices=acc(np.asarray(m.f).reshape(-1),'SCALAR',5123),material=MATERIALS.index(mat))
        meshes.append(dict(name=f'{NODES[par]["name"]}_{mat}',primitives=[p]));nodes.append(dict(name=meshes[-1]['name'],mesh=len(meshes)-1));nodes[par]['children'].append(len(nodes)-1)
    doc=dict(asset=dict(version='2.0',generator='ChainMorningstarVR reference mesh generator'),scene=0,scenes=[dict(nodes=[0])],nodes=nodes,meshes=meshes,materials=mats,images=images,textures=textures,samplers=[dict(wrapS=10497,wrapT=10497)],buffers=[dict(byteLength=len(chunks))],bufferViews=views,accessors=accessors)
    data=json.dumps(doc,separators=(',',':')).encode();data+=b' '*((-len(data))%4);chunks+=b'\0'*((-len(chunks))%4)
    out.write_bytes(struct.pack('<4sII',b'glTF',2,12+8+len(data)+8+len(chunks))+struct.pack('<I4s',len(data),b'JSON')+data+struct.pack('<I4s',len(chunks),b'BIN\0')+chunks)

def write(out,texture_dir):
    dirs=build(texture_dir);out.mkdir(parents=True,exist_ok=True)
    # Text interchange intentionally readable and simple to independently inspect.
    with (out/'reference_mesh.cms').open('w') as f:
        f.write(f'CMSMESH 1\n{len(NODES)} {len(MESHES)} {len(COLLISION)}\n')
        for n in NODES:f.write(f'{n["name"]} {n["parent"]} '+ ' '.join(map(str,n['t']+np.asarray(n['r']).flatten().tolist()))+'\n')
        for i,((par,mat),m) in enumerate(MESHES.items()):
            assert len(m.v)<65536 and len(m.f)<65536
            f.write(f'CMS_{NODES[par]["name"]}_{mat} {par} {MATERIALS.index(mat)} {len(m.v)} {len(m.f)}\n')
            for v,n,uv in zip(m.v,m.n,m.uv):f.write(' '.join(f'{x:.9g}' for x in v+n+uv)+'\n')
            for t in m.f:f.write(' '.join(map(str,t))+'\n')
        for h in COLLISION:
            f.write(f'{len(h["v"])} {len(h["planes"])} {h["margin"]}\n')
            for p in h['v']+h['planes']:f.write(' '.join(f'{x:.9g}' for x in p)+'\n')
    glb(out/'ChainMorningstar_reference.glb',texture_dir)
    vertices=[]
    for (parent,_),m in MESHES.items():
        r,t=world_transform(parent);vertices.extend(np.asarray(m.v)@r.T+t)
    v=np.asarray(vertices)
    manifest=dict(generator='reference_mesh_v3_curved_textured_emblem',visual_only_preview=True,head_directions=dirs,vertices=len(v),triangles=sum(len(m.f) for m in MESHES.values()),skyrim_units_per_meter=SU,bounds_m=[v.min(0).tolist(),v.max(0).tolist()],bounds_skyrim_units=[(v.min(0)*SU).tolist(),(v.max(0)*SU).tolist()],nodes=NODES,collision_hulls=len(COLLISION),sculpt_features=FEATURES,emblem=EMBLEM,reference_fidelity_limitations=['Single reference image has no rear/underside views; rear decoration is inferred.','The supplied full diamond emblem is mapped onto a curved closed plaque; small relief follows image luminance and is not a recovered sculpture.','Surface response requires Skyrim VR lighting verification.'])
    (out/'asset_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['nodes','head_directions','sculpt_features']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--textures',type=Path,required=True);args=p.parse_args();write(args.out,args.textures)
