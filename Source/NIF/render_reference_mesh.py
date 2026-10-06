"""CPU triangle rasterizer for the exact generated mesh (no image generation).
Material illustration only; not a claim about Skyrim shader or runtime physics.
"""
from pathlib import Path
import argparse,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import generate_reference_mesh as g

def mip_chain(path,mode):
    im=Image.open(path).convert(mode);levels=[]
    while True:
        levels.append(np.asarray(im).astype(float))
        if im.size==(1,1):break
        im=im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)
    return levels

def bilinear(levels,uv,lod):
    a=levels[lod];height,width=a.shape[:2]
    x=uv[:,0]*width-.5;y=(1-uv[:,1])*height-.5
    xi=np.floor(x).astype(int);yi=np.floor(y).astype(int);fx=x-xi;fy=y-yi
    if a.ndim==3:fx=fx[:,None];fy=fy[:,None]
    v00=a[yi%height,xi%width];v10=a[yi%height,(xi+1)%width]
    v01=a[(yi+1)%height,xi%width];v11=a[(yi+1)%height,(xi+1)%width]
    return (v00*(1-fx)+v10*fx)*(1-fy)+(v01*(1-fx)+v11*fx)*fy

def render(texture_dir,out,size=1600,part="full"):
    head_only=part=="head"
    cam=g.unit([.19,-.065,1]);bx=g.unit([cam[2],0,-cam[0]]);by=np.cross(cam,bx)
    a=.78 if part!="handle" else .28
    u=math.cos(a)*bx-math.sin(a)*by;v=math.sin(a)*bx+math.cos(a)*by
    basis=np.array([u,v,cam]);allv=[];objects=[]
    for (par,mat),m in g.MESHES.items():
        if head_only and par!=16:continue
        if part=="handle" and par!=0:continue
        r,t=g.world_transform(par);world=np.asarray(m.v)@r.T+t;n=np.asarray(m.n)@r.T
        objects.append((world@basis.T,n,np.asarray(m.uv),np.asarray(m.f),mat,world));allv.extend(world@basis.T)
    arr=np.asarray(allv);mi=arr.min(0);ma=arr.max(0);scale=(size-180)/max(ma[0]-mi[0],ma[1]-mi[1]);center=(mi+ma)/2
    img=np.full((size,size,3),242,dtype=np.float32);depth=np.full((size,size),-1e10)
    tex={k:mip_chain(texture_dir/f'cms_{k}_d.png','RGB') for k in ['metal','wood','leather']}
    normal_rgba={k:mip_chain(texture_dir/f'cms_{k}_n.png','RGBA') for k in ['metal','wood','leather']}
    envmask=mip_chain(texture_dir/'cms_metal_m.png','L')
    light=g.unit([-.4,.5,1]);fill=g.unit([.65,-.4,.6]);half=g.unit(light+cam)
    for pos,n,uv,faces,mat,world in objects:
        p=pos.copy();p[:,0]=(p[:,0]-center[0])*scale+size/2;p[:,1]=size/2-(p[:,1]-center[1])*scale
        base='wood' if mat=='wood' else 'leather' if mat in ['leather','cord'] else 'metal'
        tint={'darksteel':np.array([.30,.32,.35]),'edge':np.array([1.35]*3),'bronze':np.array([1,.76,.44]),'cord':np.array([.90,.85,.75])}.get(mat,np.ones(3))
        for ids in faces:
            tri=p[ids];a,b,c=tri[:,:2];den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-5:continue
            lo=np.maximum(np.floor(tri[:,:2].min(0)).astype(int),0);hi=np.minimum(np.ceil(tri[:,:2].max(0)).astype(int),size-1)
            if np.any(hi<lo):continue
            yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];xx=xx+.5;yy=yy+.5
            w0=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            w1=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w2=1-w0-w1
            z=w0*tri[0,2]+w1*tri[1,2]+w2*tri[2,2]
            target=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=(w0>=0)&(w1>=0)&(w2>=0)&(z>target)
            if not mask.any():continue
            weights=np.array([w0[mask],w1[mask],w2[mask]]).T
            norm=weights@n[ids];norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-10)
            tx=weights@uv[ids]
            dp1=b-a;dp2=c-a;duv1=uv[ids[1]]-uv[ids[0]];duv2=uv[ids[2]]-uv[ids[0]]
            ds=dp1[0]*dp2[1]-dp1[1]*dp2[0]
            ux=(duv1*dp2[1]-duv2*dp1[1])/ds;uy=(-duv1*dp2[0]+duv2*dp1[0])/ds
            footprint=1024*max(np.linalg.norm(ux),np.linalg.norm(uy))
            lod=min(10,max(0,int(math.log2(max(1,footprint)))))
            color=bilinear(tex['wood' if mat=='cord' else base],tx,lod)*tint
            sampled_normal=bilinear(normal_rgba[base],tx,lod)
            e1=world[ids[1]]-world[ids[0]];e2=world[ids[2]]-world[ids[0]];d1=uv[ids[1]]-uv[ids[0]];d2=uv[ids[2]]-uv[ids[0]];det=d1[0]*d2[1]-d1[1]*d2[0]
            if abs(det)>1e-6:
                tangent=g.unit((e1*d2[1]-e2*d1[1])/det);bitangent=g.unit((e2*d1[0]-e1*d2[0])/det)
                nm=sampled_normal[:,:3]/127.5-1;norm=norm*nm[:,2,None]+tangent*nm[:,0,None]+bitangent*nm[:,1,None];norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-10)
            diffuse=.28+.82*np.maximum(norm@light,0)+.25*np.maximum(norm@fill,0)
            specmask=sampled_normal[:,3]/255
            rough=10 if base!='metal' else 28
            spec=(np.maximum(norm@half,0)**rough)*specmask*(65 if base!='metal' else 255)
            # Authored metal environment mask suppresses reflections in pits.
            refl=(np.maximum(norm@fill,0)**8)*(0 if base!='metal' else 105*bilinear(envmask,tx,lod)/255)
            rgb=np.clip(color*diffuse[:,None]+spec[:,None]+refl[:,None]*[.87,.94,1],0,255)
            target[mask]=z[mask];img[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=rgb
    im=Image.fromarray(img.astype('uint8'));d=ImageDraw.Draw(im)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    title={'full':'CHAIN MORNINGSTAR / SCULPTED MESH','head':'FORGED IRON / SCULPTED MESH','handle':'TAPERED WOOD + WORN LEATHER / SCULPTED MESH'}[part]
    d.text((38,26),title,fill=(35,41,46),font=font)
    d.text((38,size-46),f'Asset preview  |  {sum(len(m.f) for m in g.MESHES.values()):,} triangles  |  Skyrim VR verification pending',fill=(75,79,84),font=font)
    im.save(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--textures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();g.build();args.out.mkdir(parents=True,exist_ok=True)
    render(args.textures,args.out/'ChainMorningstar_mesh_preview.png');render(args.textures,args.out/'ChainMorningstar_head_detail.png',part='head');render(args.textures,args.out/'ChainMorningstar_handle_detail.png',part='handle')
