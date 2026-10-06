"""Deterministic reference-based asset geometry; no Blender or prior weapon asset.

Writes an interchange file consumed by export_reference_nif.cpp and a glTF 2.0
binary with the SAME vertices, normals, UVs and hierarchy for inspection.
Distances are meters here; the NIF exporter converts only visual vertices/node
translations to Skyrim units. Havok hull vertices stay in meters.
"""
from __future__ import annotations
import json, math, struct, argparse
from pathlib import Path
import numpy as np
from PIL import Image

SU = 69.99125
NODES = []
MESHES = {}
COLLISION = []
MATERIALS = ['metal', 'wood', 'leather', 'darksteel', 'edge', 'cord', 'bronze']

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
    for i in range(count if closed else count-1):
        k=(i+1)%count
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

def build():
    root=node('CMS_ROOT',-1)
    anchor=node('CMS_ChainAnchor',root,(0,.4,0),[[1,0,0],[0,0,1],[0,-1,0]])
    links=[]
    for i in range(14):
        a=(i%2)*math.pi/2;rot=[[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]]
        links.append(node(f'CMS_LinkNode_{i:02d}',anchor,(0,0,.035+i*.84/13),rot))
    head=node('CMS_HeadNode',anchor,(0,0,1.065))
    # Tapered hardwood with steel ferrules; grip origin remains inside leather.
    lathe(root,'wood',[(-.16,0),(-.159,.028),(-.11,.03),(.18,.032),(.345,.032),(.4,.025),(.4,0)])
    lathe(root,'leather',[(-.115,.031),(-.111,.037),(-.095,.038),(.117,.036),(.136,.034),(.14,.03)])
    # Paired helical cords recreate the conspicuous diamond lacing in the image.
    for sign in [-1,1]:
        pts=[]
        for t in np.linspace(0,1,241):
            a=sign*(t*2*math.pi*4.6)+.4;r=.038-(.002*t)
            pts.append([r*math.cos(a),-.108+t*.237,r*math.sin(a)])
        tube(root,'cord',pts,.0019,6)
    for y,r,L in [(-.145,.044,.044),(.3725,.047,.055)]:
        profile=[(y-L/2,.031),(y-L/2+.003,r-.005),(y-L/2+.007,r),(y+L/2-.007,r),(y+L/2-.003,r-.004),(y+L/2,.031)]
        lathe(root,'metal',profile)
        for a in [y-L/2+.006,y+L/2-.006]:ring(root,'edge',r,.0025,(0,a,0))
        rune_band(root,(0,y,0),radius=r+.0006,length=L*.9)
    # Reference has a distinct free pommel ring, never a spherical pommel.
    lathe(root,'metal',[(-.181,.014),(-.178,.022),(-.165,.024),(-.156,.020)])
    ring(root,'bronze',.052,.0085,(0,-.226,0),axis=(0,0,1),segs=64)
    ring(root,'metal',.025,.009,(0,.405,0),axis=(1,0,0),stretch=1.22)
    for i,ln in enumerate(links):
        # Runtime writes alternating roll onto this node, so mesh stays XZ.
        u=np.array([1,0,0]);w=np.array([0,0,1])
        pts=[]
        for t in np.linspace(0,2*math.pi,40,endpoint=False):
            pts.append(u*(.0369*math.cos(t))+w*(.0603*math.sin(t)))
        tube(ln,'metal',pts,.0105,10,True)
    sphere(head,'metal')
    dirs=[]
    for i in range(8): dirs.append([math.cos(i*math.pi/4+math.pi/8),0,math.sin(i*math.pi/4+math.pi/8)])
    r=math.sqrt(1-.64**2)
    for y in [-.64,.64]:
        for i in range(3):dirs.append([r*math.cos(i*2*math.pi/3),y,r*math.sin(i*2*math.pi/3)])
    # Collar at each spike base creates riveted socket silhouette.
    for d in dirs:
        lathe(head,'metal',[(.146,.024),(.151,.045),(.16,.046),(.174,.039),(.229,.006),(.24,0)],axis=d,segs=16)
        ring(head,'edge',.0435,.0016,np.array(d)*.159,axis=d,segs=24)
    # Head chain socket finishes at z=-.170, connecting to the last oval link.
    lathe(head,'metal',[(-.202,.023),(-.198,.035),(-.167,.035),(-.154,.028)],axis=(0,0,1))
    rune_band(head,(0,0,-.181),axis=(0,0,1),radius=.0355,length=.026,segments=6)
    ring(head,'metal',.029,.008,(0,0,-.212),axis=(0,1,0),stretch=1.13)
    # Diamond frame + black recessed field + raised hand-traced dragon silhouette.
    crest_starts={k:len(m.v) for k,m in MESHES.items() if k[0]==head}
    diamond=[(0,.146),(-.070,0),(0,-.146),(.070,0)]
    plate(head,'metal',diamond,-.150,-.125)
    for scale,rad,yy in [(1,.004,-.155),(.88,.0026,-.158),(.74,.0017,-.162)]:
        tube(head,'edge',[[x*scale,yy,z*scale] for x,z in diamond],rad,6,True)
    plate(head,'darksteel',[(x*.77,z*.77) for x,z in diamond],-.159,-.148)
    # Curved central body, antlers, split wings and tapered tail. This is modelled
    # relief, not a projected image; the unseen rear remains unadorned.
    dragon=[(-.004,.103),(.006,.088),(.002,.078),(.004,.069),(.014,.067),(.018,.058),(.015,.047),(.005,.038),(-.005,.029),(-.009,.018),(-.006,.007),(.002,-.002),(.007,-.016),(.003,-.039),(-.007,-.064),(-.009,-.083),(-.003,-.106),(-.015,-.090),(-.017,-.072),(-.012,-.051),(-.008,-.032),(-.013,-.013),(-.019,.005),(-.019,.023),(-.013,.037),(.001,.048),(.008,.056),(.005,.061),(-.006,.060),(-.012,.066),(-.012,.080)]
    wing_left=[(-.016,.036),(-.026,.051),(-.031,.077),(-.035,.050),(-.032,.031),(-.028,.017),(-.032,.005),(-.026,.008),(-.020,-.003),(-.024,-.018),(-.017,-.012),(-.012,-.022),(-.014,.005),(-.022,.021)]
    # Wings, horns and talons are separate pieces of filled embossed steel.
    wing_right=[(-x,z-.008) for x,z in wing_left]
    horn=[(-.009,.080),(-.021,.093),(-.017,.073),(-.008,.068)]
    talon=[(-.009,-.024),(-.025,-.033),(-.029,-.053),(-.023,-.045),(-.018,-.053),(-.018,-.039),(-.006,-.035)]
    for outline in [dragon,wing_left,wing_right,horn,talon,[(-x,z) for x,z in talon]]:
        plate(head,'edge',outline,-.170,-.164)
        tube(head,'edge',[[x,-.1708,z] for x,z in outline],.0006,5,True)
    # The reference emblem stands almost upright while the weapon lies diagonally.
    angle=math.pi/4;rot=np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]])
    for k,m in MESHES.items():
        if k[0]==head:
            start=crest_starts.get(k,0);m.v[start:]=(np.asarray(m.v[start:])@rot.T).tolist();m.n[start:]=(np.asarray(m.n[start:])@rot.T).tolist()
    # Engraved web bands on visible sphere quadrants, clear of plaque and spikes.
    for sign in [-1,1]:
        for z0 in [-.10,-.045,.025,.085]:
            pts=[]
            for x,z in [(sign*.079,z0),(sign*.101,z0+.014),(sign*.125,z0+.003),(sign*.116,z0-.015),(sign*.096,z0-.014)]:
                rr=.16**2-x*x-z*z
                if rr>0:pts.append([x,-math.sqrt(rr)-.001,z])
            if len(pts)>2:tube(head,'darksteel',pts,.0018,5)
    # Independent low-poly convex collision hulls; all planes generated by scipy
    # in a separate pass, never derived from a decorative surface normal.
    from scipy.spatial import ConvexHull
    points=[]
    for z in [-1,-.75,-.35,0,.35,.75,1]:
        rad=math.sqrt(max(0,1-z*z))
        for a in np.linspace(0,2*math.pi,16,endpoint=False): points.append([.16*rad*math.cos(a),.16*rad*math.sin(a),.16*z])
    def hull(points,margin):
        points=np.unique(np.round(points,9),axis=0);h=ConvexHull(points)
        COLLISION.append(dict(v=points[h.vertices].tolist(),planes=np.unique(np.round(h.equations,9),axis=0).tolist(),margin=margin))
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
    images=[];textures=[]
    for base in ['metal','wood','leather']:
        images.append(dict(bufferView=raw((texture_dir/f'cms_{base}_d.png').read_bytes()),mimeType='image/png'))
        textures.append(dict(source=len(images)-1,sampler=0))
    mats=[]
    for name in MATERIALS:
        base={'wood':1,'leather':2,'cord':2}.get(name,0)
        factor={'darksteel':[.31,.33,.35,1],'edge':[1,1,1,1],'cord':[1,.88,.72,1],'bronze':[1,.76,.44,1]}.get(name,[1,1,1,1])
        mats.append(dict(name=name,pbrMetallicRoughness=dict(baseColorTexture={'index':base},baseColorFactor=factor,metallicFactor=0 if name in ['wood','leather','cord'] else .85,roughnessFactor=.36 if name not in ['wood','leather','cord'] else .72)))
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
    dirs=build();out.mkdir(parents=True,exist_ok=True)
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
    manifest=dict(generator='reference_mesh_v1',visual_only_preview=True,head_directions=dirs,vertices=len(v),triangles=sum(len(m.f) for m in MESHES.values()),skyrim_units_per_meter=SU,bounds_m=[v.min(0).tolist(),v.max(0).tolist()],bounds_skyrim_units=[(v.min(0)*SU).tolist(),(v.max(0)*SU).tolist()],nodes=NODES,collision_hulls=len(COLLISION),reference_fidelity_limitations=['Single reference image has no rear/underside views; rear decoration is inferred.','Dragon relief is hand-modelled from the visible silhouette, not an exact scan.','Surface response requires Skyrim VR lighting verification.'])
    (out/'asset_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['nodes','head_directions']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--textures',type=Path,required=True);args=p.parse_args();write(args.out,args.textures)
