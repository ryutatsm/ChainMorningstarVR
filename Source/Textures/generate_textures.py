from PIL import Image, ImageFilter
import numpy as np, math
from pathlib import Path

OUT=Path(__file__).resolve().parents[2] / 'build' / 'textures' / 'weapons' / 'ChainMorningstarVR'
OUT.mkdir(parents=True,exist_ok=True)
N=1024
rng=np.random.default_rng(20261006)

def blur(a,r):
    im=Image.fromarray(np.clip(a*255,0,255).astype('uint8'),'L').filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im,dtype=np.float32)/255.0

def normal_from_height(h,strength=3.0):
    dx=np.roll(h,-1,1)-np.roll(h,1,1)
    dy=np.roll(h,-1,0)-np.roll(h,1,0)
    nx=-dx*strength; ny=-dy*strength; nz=np.ones_like(h)
    norm=np.sqrt(nx*nx+ny*ny+nz*nz)+1e-8
    rgb=np.stack([(nx/norm*0.5+0.5),(ny/norm*0.5+0.5),(nz/norm*0.5+0.5)],axis=2)
    return (np.clip(rgb,0,1)*255).astype('uint8')

def save_rgb(arr,name):
    Image.fromarray(np.clip(arr,0,255).astype('uint8'),'RGB').save(OUT/name)

y,x=np.mgrid[0:N,0:N]
noise1=blur(rng.random((N,N)),1.1)
noise2=blur(rng.random((N,N)),5.0)
noise3=blur(rng.random((N,N)),18.0)
pits=(noise1*0.50+noise2*0.30+noise3*0.20)
hammer=np.zeros((N,N),np.float32)
for _ in range(260):
    cx=rng.integers(0,N); cy=rng.integers(0,N); r=rng.uniform(4,18)
    d2=(x-cx)**2+(y-cy)**2
    hammer -= np.exp(-d2/(2*r*r))*rng.uniform(.08,.28)

scr=np.zeros((N,N),np.float32)
for _ in range(420):
    ang=rng.choice([0,math.pi/2,math.pi/4,-math.pi/4])+rng.normal(0,.08)
    cx=rng.uniform(0,N); cy=rng.uniform(0,N)
    L=rng.uniform(20,180); w=rng.uniform(.5,1.8)
    ca,sa=math.cos(ang),math.sin(ang)
    u=(x-cx)*ca+(y-cy)*sa; v=-(x-cx)*sa+(y-cy)*ca
    scr -= np.exp(-(v*v)/(2*w*w))*((np.abs(u)<L/2).astype(np.float32))*rng.uniform(.02,.09)

height_m=np.clip(.50 + (pits-.5)*.18 + hammer + scr,0,1)
oxide=blur(rng.random((N,N)),26)
base=np.array([105,111,116],np.float32)
metal=np.empty((N,N,3),np.float32)
for c in range(3):
    metal[:,:,c]=base[c]*(0.76+0.34*height_m)*(0.92+0.12*oxide)
metal += ((noise2-.5)*12)[...,None]
metal=np.clip(metal,24,190)
save_rgb(metal,'cms_metal_d.png')
Image.fromarray(normal_from_height(height_m,8.5),'RGB').save(OUT/'cms_metal_n.png')
mask=np.clip(0.18 + 0.72*(height_m**1.35) - .18*(oxide-.5),0.05,0.92)
Image.fromarray((mask*255).astype('uint8'),'L').save(OUT/'cms_metal_m.png')

warp=blur(rng.random((N,N)),24)
xx=(x + (warp-.5)*85.0)
grain=0.5+0.22*np.sin(xx*0.055 + np.sin(y*0.012)*1.5)+0.08*np.sin(xx*0.19)
pores=blur(rng.random((N,N)),1.0)
height_w=np.clip(.5+(grain-.5)*.55+(pores-.5)*.10,0,1)
wood=np.zeros((N,N,3),np.float32)
wood[:,:,0]=80+75*grain
wood[:,:,1]=38+45*grain
wood[:,:,2]=14+22*grain
wood*= (0.90+0.16*blur(rng.random((N,N)),12))[...,None]
save_rgb(wood,'cms_wood_d.png')
Image.fromarray(normal_from_height(height_w,5.0),'RGB').save(OUT/'cms_wood_n.png')

coarse=blur(rng.random((N,N)),2.4)
fine=blur(rng.random((N,N)),0.7)
height_l=np.clip(.5+(coarse-.5)*.35+(fine-.5)*.15,0,1)
wear=0.5+0.5*np.sin((x+y)*0.055)
leather=np.zeros((N,N,3),np.float32)
leather[:,:,0]=42+35*height_l+7*wear
leather[:,:,1]=20+20*height_l+4*wear
leather[:,:,2]=12+12*height_l+2*wear
save_rgb(leather,'cms_leather_d.png')
Image.fromarray(normal_from_height(height_l,4.8),'RGB').save(OUT/'cms_leather_n.png')

print('CMS_TEXTURE_SOURCE_OK', OUT)\n# CI verification branch marker.
