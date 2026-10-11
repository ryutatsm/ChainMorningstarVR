"""Explicit audit6 retopology with an inclusive 4,000-triangle NIF budget.

Samples authored surfaces; never runs the original asset generators. Decorative
relief is baked. Runtime nodes, collision and native blood policy stay intact.
"""
import argparse,json,sys,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cms_io import parse,sha256,BASELINE_SHA256,AUDIT6_COMMIT
import optimize_audit6 as bake_tools
from optimize_audit6 import geometry,destroy,bake,bake_alpha,install_image,pixel_array,select,transfer_normals
from surface_contract import surface,barycentric,distance_report,topology

def new_mesh(high,positions,uv,faces):
    p=np.asarray(positions);f=np.asarray(faces,dtype=int)
    mesh=bpy.data.meshes.new(high.name+'_LOW');mesh.from_pydata(p.tolist(),[],f.tolist());mesh.update()
    layer=mesh.uv_layers.new(name='CMS_UV')
    for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
    for poly in mesh.polygons:poly.use_smooth=True
    ob=high.copy();ob.data=mesh;bpy.data.collections['02_Visuals_EDIT'].objects.link(ob)
    ob.data.materials.append(high.active_material.copy())
    return ob

def grid_surface(vertices,rows,cols,v_steps,u_steps):
    # Piece-local UVs, not an atlas shared by unrelated components.
    a=np.asarray(vertices).reshape(rows,cols,8);p=a[:,:,:3];uv=a[:,:,6:8]
    out=[];tex=[];faces=[]
    for y in v_steps:
        j=min(int(y),rows-2);t=y-j
        for x in u_steps:
            i=min(int(x),cols-2);s=x-i
            # Bilinear sampling of authored positions and authored UV corners.
            out.append((1-t)*((1-s)*p[j,i]+s*p[j,i+1])+t*((1-s)*p[j+1,i]+s*p[j+1,i+1]))
            tex.append((1-t)*((1-s)*uv[j,i]+s*uv[j,i+1])+t*((1-s)*uv[j+1,i]+s*uv[j+1,i+1]))
    nc=len(u_steps)
    for j in range(len(v_steps)-1):
        for i in range(nc-1):
            k=j*nc+i;faces.extend([[k,k+1,k+nc],[k+1,k+nc+1,k+nc]])
    return np.asarray(out),np.asarray(tex),np.asarray(faces)

def orient_grid(p,f,source,uv=None):
    old=np.array(source['vertices']);oldf=np.array(source['faces']);tree=surface(old[:,:3],oldf)
    if uv is not None:
        t=old[oldf,6:8];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];areas=a[:,0]*b[:,1]-a[:,1]*b[:,0]
        signs=set(np.sign(areas[np.abs(areas)>1e-10]))
        if len(signs)==1:
            t=uv[f];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];area=a[:,0]*b[:,1]-a[:,1]*b[:,0]
            f[area*next(iter(signs))<0]=f[area*next(iter(signs))<0][:,[0,2,1]]
            return f
    normals=np.cross(old[oldf[:,1],:3]-old[oldf[:,0],:3],old[oldf[:,2],:3]-old[oldf[:,0],:3])
    for k,tri in enumerate(f):
        _,_,i,_=tree.find_nearest(Vector(p[tri].mean(0)))
        n=np.cross(p[tri[1]]-p[tri[0]],p[tri[2]]-p[tri[0]])
        if np.dot(n,normals[i])<0:f[k]=tri[[0,2,1]]
    return f

def joined(parts):
    p=[];uv=[];f=[]
    for q,t,g in parts:
        f.extend(g+len(p));p.extend(q);uv.extend(t)
    return np.array(p),np.array(uv),np.array(f)

def tube_grid(m,count,sides,path_steps,cross_steps,parts=1):
    stride=(count+1)*(sides+1);pieces=[]
    for k in range(parts):
        pieces.append(grid_surface(m['vertices'][k*stride:(k+1)*stride],count+1,sides+1,
             np.linspace(0,count,path_steps+1),np.linspace(0,sides,cross_steps+1)))
    return joined(pieces)

def lathe_grid(m,profile,steps,selected,parts=1):
    stride=profile*49;pieces=[]
    for k in range(parts):
        pieces.append(grid_surface(m['vertices'][k*stride:(k+1)*stride],profile,49,selected,np.linspace(0,48,steps+1)))
    return joined(pieces)

def ball(m):
    # Sample only the visible forged core. The hidden plaque backing is removed.
    old=np.asarray(m['vertices']);f=np.asarray(m['faces'])
    # The first 4,096 triangles are the core's 64x32 grid (degenerate poles
    # were filtered by the original author); group is identified from .blend.
    high=bpy.data.objects[m['name']];group=high.vertex_groups['hammered_iron_core']
    used={v.index for v in high.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups)}
    core=f[np.all(np.isin(f,list(used)),axis=1)];tree=surface(old[:,:3],core)
    p=[];uv=[];faces=[];longitude=16;latitude=8
    for j in range(latitude+1):
        theta=j/latitude*math.pi
        for i in range(longitude+1):
            phi=i/longitude*2*math.pi;d=np.array([math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta)])
            near,_,_,_=tree.find_nearest(Vector(d*.12));p.append(np.array(near));uv.append([i/longitude,j/latitude])
    for j in range(latitude):
        for i in range(longitude):
            a=j*(longitude+1)+i;b=a+longitude+1
            if j:faces.append([a,b,a+1])
            if j<latitude-1:faces.append([a+1,b,b+1])
    return np.array(p),np.array(uv),np.array(faces)

def spikes(m):
    # Each original spike has an 18x25 lateral grid plus its flattened tip cap.
    # Preserve all 14 directions, base, tip, UV seam and cap. Six-sided taper.
    pieces=[];stride=18*25+26
    assert len(m['vertices'])==14*stride,(len(m['vertices']),stride)
    for k in range(14):
        rows=m['vertices'][k*stride:k*stride+18*25]
        # The lower four authored rows penetrate the ball. Retain the external
        # taper from its widest shoulder, preserving the 14 original tip caps.
        p,uv,f=grid_surface(rows,18,25,[4,17],np.linspace(0,24,7))
        # A fan triangulation of the six distinct terminal ring vertices.
        for i in range(1,5):f=np.vstack([f,[7,7+i,7+i+1]])
        pieces.append((p,uv,f))
    return joined(pieces)

def emblem(m):
    # Flat relief on a curved diamond: no image-height geometry remains.
    corners=np.array([[626.,10.],[999.,583.],[625.,1202.],[251.,583.]])
    center=np.array([625.,606.]);sub=5;pixels=[];faces=[];lookup={}
    def index(pixel):
        key=tuple(np.round(pixel,8))
        if key not in lookup:lookup[key]=len(pixels);pixels.append(pixel)
        return lookup[key]
    for side in range(4):
        a=corners[side];b=corners[(side+1)%4];indices={}
        for i in range(sub+1):
            for j in range(sub+1-i):indices[i,j]=index(center+(a-center)*i/sub+(b-center)*j/sub)
        for i in range(sub):
            for j in range(sub-i):
                faces.append([indices[i,j],indices[i+1,j],indices[i,j+1]])
                if i+j<sub-1:faces.append([indices[i+1,j],indices[i+1,j+1],indices[i,j+1]])
    pixel=np.array(pixels);scale=.256*.75/(1202-10)
    x=(pixel[:,0]-625)*scale;z=(606-pixel[:,1])*scale
    d=np.column_stack([x,-np.sqrt(.12**2-x*x-z*z),z])/.12
    a=math.pi/3;rot=np.array([[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]])
    p=d*.1216@rot.T;uv=np.column_stack([pixel[:,0]/1253,1-pixel[:,1]/1253])
    return p,uv,np.array(faces)

def uv_coverage(obj,size=1024):
    obj.data.calc_loop_triangles();mask=np.zeros((size,size),dtype=bool)
    layer=obj.data.uv_layers[0]
    for tri in obj.data.loop_triangles:
        t=np.array([layer.data[i].uv[:] for i in tri.loops])*size
        lo=np.maximum(np.floor(t.min(0)).astype(int),0);hi=np.minimum(np.ceil(t.max(0)).astype(int),size-1)
        if np.any(hi<lo):continue
        y,x=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];p=np.stack([x+.5,y+.5],axis=-1)
        a=t[1]-t[0];b=t[2]-t[0];z=p-t[0];den=a[0]*b[1]-a[1]*b[0]
        if abs(den)<1e-10:continue
        u=(z[:,:,0]*b[1]-z[:,:,1]*b[0])/den;v=(a[0]*z[:,:,1]-a[1]*z[:,:,0])/den
        # Exclude boundary texels from numerical rasterization disagreement.
        inside=(u>.002)&(v>.002)&(u+v<.998)
        mask[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=inside
    return mask

def retopo(a):
    a.blend=a.blend.resolve();a.out=a.out.resolve();a.textures=a.textures.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
    cms=parse(bpy.data.texts['AUDIT6_BASELINE.cms'].as_string().encode())
    a.textures.mkdir(parents=True,exist_ok=True);a.out.parent.mkdir(parents=True,exist_ok=True)
    bake_tools.DEBUG_DIR=a.textures/'debug';bake_tools.DEBUG_DIR.mkdir(exist_ok=True)
    # Restore the known intact audit6 metal preview, without changing game DDS.
    if a.metal_preview:
        old=bpy.data.images['cms_metal_n.png'];im=bpy.data.images.load(str(a.metal_preview.resolve()))
        im.colorspace_settings.name='Non-Color';im.alpha_mode='CHANNEL_PACKED';old.user_remap(im)
        bpy.data.images.remove(old);im.name='cms_metal_n.png';im.pack();im.filepath='//textures/cms_metal_n.png'
    highs={m['name']:bpy.data.objects[m['name']] for m in cms['meshes']};lows={};reports=[]
    for m in cms['meshes']:
        name=m['name'];high=highs[name];kind=name.rsplit('_',1)[1]
        if kind=='cord':continue
        if kind in ('wood','leather'):
            nr,nc,around=(75,73,12) if kind=='wood' else (91,89,16)
            p,uv,f=grid_surface(m['vertices'],nr,nc,np.linspace(0,nr-1,6),np.linspace(0,nc-1,around+1))
            low=new_mesh(high,p,uv,orient_grid(p,f,m,uv))
        else:
            if 'LinkNode' in name:part=tube_grid(m,40,10,10,4)
            elif name=='CMS_CMS_ROOT_edge':part=tube_grid(m,48,10,8,3,4)
            elif kind=='bronze':part=tube_grid(m,64,10,8,4)
            elif kind=='chain':part=tube_grid(m,48,10,8,4)
            elif kind=='ring':part=lathe_grid(m,4 if 'HeadNode' in name else 6,8,[0,1,3] if 'HeadNode' in name else [0,2,3,5],1 if 'HeadNode' in name else 2)
            elif name=='CMS_CMS_ROOT_metal':part=lathe_grid(m,4,6,[0,2,3])
            elif kind=='metal':part=ball(m)
            elif kind=='spike':part=spikes(m)
            elif kind=='emblem':part=emblem(m)
            else:raise ValueError(name)
            p,uv,f=part;f=orient_grid(p,f,m,uv);low=new_mesh(high,p,uv,f)
        # Preserve smooth authored shading across coincident UV seams. A low
        # polygon count must not introduce hard seams or faceted normal bands.
        transfer_normals(low,m)
        lows[name]=low;q,g=geometry(low)
        reports.append(dict(mesh=name,before_triangles=len(m['faces']),after_triangles=len(g)))
        print('RETOPO',name,len(g),flush=True)
    total=sum(r['after_triangles'] for r in reports)
    blood=sum(r['after_triangles'] for r in reports if r['mesh'] in ('CMS_CMS_HeadNode_metal','CMS_CMS_HeadNode_spike','CMS_CMS_HeadNode_emblem'))*2
    if total+blood>4000:raise ValueError(f'Inclusive budget exceeded: {total}+{blood}')
    textures=[]
    bpy.context.scene.render.engine='CYCLES';bpy.context.scene.cycles.device='CPU';bpy.context.scene.cycles.samples=16
    for base in ('wood','leather','emblem'):
        name='CMS_CMS_'+('HeadNode' if base=='emblem' else 'ROOT')+'_'+base
        low=lows[name];sources=[highs[name]]
        if base=='leather':sources.append(highs['CMS_CMS_ROOT_cord'])
        alpha=pixel_array(bpy.data.images[f'cms_{base}_n.png'])[:,:,3].copy()
        options=dict(cage_extrusion=.008,max_ray_distance=.016) if base=='leather' else {}
        coverage=uv_coverage(low)
        normal=bake(low,sources,'NORMAL',base+'_n',**options)
        if base=='leather':
            diffuse=bake(low,sources,'DIFFUSE','leather_d',**options);alpha=bake_alpha(low,sources,coverage=coverage,**options)
            textures.append(install_image(diffuse,'cms_leather_d.png',a.textures,np.ones((1024,1024)),coverage=coverage))
        textures.append(install_image(normal,f'cms_{base}_n.png',a.textures,alpha,coverage=coverage))
    for high in highs.values():destroy(high)
    for name,low in lows.items():
        low.name=name;low.data.name=name
        mat=low.active_material;canonical='CMS_'+mat.name.split('CMS_',1)[1].split('.')[0]
        old=bpy.data.materials.get(canonical)
        if old and old!=mat and old.users==0:bpy.data.materials.remove(old);old=None
        if old and old!=mat:low.data.materials[0]=old
        else:mat.name=canonical
    for name in ('cms_cord_d.png','cms_cord_n.png'):bpy.data.images[name].use_fake_user=True
    manifest=dict(format='audit6-under4k-v2',baseline_cms_sha256=BASELINE_SHA256,baseline_commit=AUDIT6_COMMIT,
       source_blend_sha256=sha256(a.blend.read_bytes()),removed_mesh='CMS_CMS_ROOT_cord',texture_bakes=textures,
       meshes=reports,before_triangles=110512,after_triangles=total,blood_triangles=blood,nif_total_triangles=total+blood,
       triangle_budget_including_blood=4000,emblem_relief='tangent-normal-map; constant-radius curved substrate',
       hidden_emblem_backing_removed=True,hidden_spike_bases_removed=True,runtime_tested=False,xedit_tested=False)
    text=bpy.data.texts.get('AUDIT6_OPTIMIZATION.json') or bpy.data.texts.new('AUDIT6_OPTIMIZATION.json')
    text.clear();text.write(json.dumps(manifest,indent=2));bpy.context.scene['cms_optimization']='audit6-under4k-v2'
    bpy.context.scene.render.bake.use_selected_to_active=False
    select([lows['CMS_CMS_HeadNode_emblem']],lows['CMS_CMS_HeadNode_emblem'])
    bpy.context.scene.camera=bpy.data.objects['Preview_Front']
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()),compress=True)
    a.out.with_suffix('.optimization.json').write_text(json.dumps(manifest,indent=2))
    print('UNDER4K_RETOPO_PASS',total,blood,total+blood,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('blend','out','textures'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--metal-preview',type=Path)
    retopo(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
