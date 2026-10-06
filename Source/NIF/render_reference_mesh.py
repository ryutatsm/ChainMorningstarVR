"""CPU triangle rasterizer for the exact generated mesh (no image generation).
Material illustration only; not a claim about Skyrim shader or runtime physics.
"""
from pathlib import Path
import argparse,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import generate_reference_mesh as g

def render(texture_dir,out,size=1600,head_only=False):
    cam=g.unit([.19,-.065,1]);bx=g.unit([cam[2],0,-cam[0]]);by=np.cross(cam,bx)
    a=0 if head_only else .78
    u=math.cos(a)*bx-math.sin(a)*by;v=math.sin(a)*bx+math.cos(a)*by
    basis=np.array([u,v,cam]);allv=[];objects=[]
    for (par,mat),m in g.MESHES.items():
        if head_only and par!=16:continue
        r,t=g.world_transform(par);world=np.asarray(m.v)@r.T+t;n=np.asarray(m.n)@r.T
        objects.append((world@basis.T,n,np.asarray(m.uv),np.asarray(m.f),mat,world));allv.extend(world@basis.T)
    arr=np.asarray(allv);mi=arr.min(0);ma=arr.max(0);scale=(size-180)/max(ma[0]-mi[0],ma[1]-mi[1]);center=(mi+ma)/2
    img=np.full((size,size,3),242,dtype=np.float32);depth=np.full((size,size),-1e10)
    tex={k:np.asarray(Image.open(texture_dir/f'cms_{k}_d.png').convert('RGB')).astype(float) for k in ['metal','wood','leather']}
    normal={k:np.asarray(Image.open(texture_dir/f'cms_{k}_n.png').convert('RGB')).astype(float)/127.5-1 for k in ['metal','wood','leather']}
    light=g.unit([-.4,.5,1]);fill=g.unit([.65,-.4,.6]);half=g.unit(light+cam)
    for pos,n,uv,faces,mat,world in objects:
        p=pos.copy();p[:,0]=(p[:,0]-center[0])*scale+size/2;p[:,1]=size/2-(p[:,1]-center[1])*scale
        base='wood' if mat=='wood' else 'leather' if mat in ['leather','cord'] else 'metal'
        tint={'darksteel':np.array([.30,.32,.35]),'edge':np.array([1.35]*3),'bronze':np.array([1,.76,.44]),'cord':np.array([1.25,1.1,.88])}.get(mat,np.ones(3))
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
            tx=weights@uv[ids];ix=(tx[:,0]*1023).astype(int)%1024;iy=((1-tx[:,1])*1023).astype(int)%1024
            color=tex[base][iy,ix]*tint
            e1=world[ids[1]]-world[ids[0]];e2=world[ids[2]]-world[ids[0]];d1=uv[ids[1]]-uv[ids[0]];d2=uv[ids[2]]-uv[ids[0]];det=d1[0]*d2[1]-d1[1]*d2[0]
            if abs(det)>1e-6:
                tangent=g.unit((e1*d2[1]-e2*d1[1])/det);bitangent=g.unit((e2*d1[0]-e1*d2[0])/det)
                nm=normal[base][iy,ix];norm=norm*nm[:,2,None]+tangent*nm[:,0,None]+bitangent*nm[:,1,None];norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-10)
            diffuse=.28+.82*np.maximum(norm@light,0)+.25*np.maximum(norm@fill,0)
            rough=12 if base!='metal' else 45;spec=(np.maximum(norm@half,0)**rough)*(15 if base!='metal' else 135)
            # Broad cool reflection gives steel curvature independent of glossy spot.
            refl=(np.maximum(norm@fill,0)**8)*(0 if base!='metal' else 42)
            rgb=np.clip(color*diffuse[:,None]+spec[:,None]+refl[:,None]*[.87,.94,1],0,255)
            target[mask]=z[mask];img[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=rgb
    im=Image.fromarray(img.astype('uint8'));d=ImageDraw.Draw(im)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    title='HEAD DETAIL / EXACT MESH' if head_only else 'CHAIN MORNINGSTAR / EXACT MESH'
    d.text((38,26),title,fill=(35,41,46),font=font)
    d.text((38,size-46),f'Asset preview  |  {sum(len(m.f) for m in g.MESHES.values()):,} triangles  |  Skyrim VR verification pending',fill=(75,79,84),font=font)
    im.save(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--textures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();g.build();args.out.mkdir(parents=True,exist_ok=True)
    render(args.textures,args.out/'ChainMorningstar_mesh_preview.png');render(args.textures,args.out/'ChainMorningstar_head_detail.png',head_only=True)
