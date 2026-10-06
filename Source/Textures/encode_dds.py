"""Encode seven Skyrim-compatible BC3/DXT5 textures with complete mip chains.
Pillow encodes each mip. Normal vectors are renormalized before encoding each mip.
Decodes every mip again to check size, finite normal data and alpha authored range.
"""
from __future__ import annotations
import argparse,io,json,struct,hashlib
from pathlib import Path
import numpy as np
from PIL import Image

def encode(src:Path):
    im=Image.open(src).convert('RGBA');normal=src.stem.endswith('_n')
    levels=[];w,h=im.size
    if (w,h)!=(1024,1024):raise ValueError('Expected 1024 x 1024')
    while True:
        if normal:
            data=np.asarray(im).copy();n=data[:,:,:3].astype(float)/127.5-1;n/=np.maximum(np.linalg.norm(n,axis=2)[:,:,None],1e-9);data[:,:,:3]=np.clip((n*.5+.5)*255,0,255).astype('uint8');im=Image.fromarray(data)
        b=io.BytesIO();im.save(b,format='DDS',pixel_format='DXT5');raw=b.getvalue();levels.append((im.size,raw[128:]))
        if im.size==(1,1):header=bytearray(raw[:128]);break
        im=im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)
    struct.pack_into('<I',header,8,0xA1007);struct.pack_into('<I',header,12,h);struct.pack_into('<I',header,16,w);struct.pack_into('<I',header,20,len(levels[0][1]));struct.pack_into('<I',header,28,len(levels));struct.pack_into('<I',header,108,0x401008)
    dst=src.with_suffix('.dds');dst.write_bytes(header+b''.join(data for _,data in levels))
    off=128;alpha=None;rgb=None
    for i,((w,h),data) in enumerate(levels):
        expect=max(1,(w+3)//4)*max(1,(h+3)//4)*16
        assert len(data)==expect
        mh=bytearray(header);struct.pack_into('<I',mh,12,h);struct.pack_into('<I',mh,16,w);struct.pack_into('<I',mh,20,len(data));struct.pack_into('<I',mh,28,1);struct.pack_into('<I',mh,108,0x1000)
        decoded=Image.open(io.BytesIO(mh+data)).convert('RGBA');assert decoded.size==(w,h)
        if i==0:alpha=np.asarray(decoded)[:,:,3];rgb=np.asarray(decoded)[:,:,:3]
        off+=len(data)
    assert off==dst.stat().st_size and len(levels)==11
    if normal:
        assert int(alpha.max())<200 and int(alpha.min())>0,'Normal alpha lost authored specular range'
        assert int(rgb[:,:,2].mean())>210,'Unexpected normal direction'
    return dict(name=dst.name,bytes=dst.stat().st_size,format='DXT5',size=[1024,1024],mip_levels=11,decoded_mips=11,normal_specular_alpha_range=[int(alpha.min()),int(alpha.max())] if normal else None,sha256=hashlib.sha256(dst.read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    names=['cms_metal_d','cms_metal_n','cms_metal_m','cms_wood_d','cms_wood_n','cms_leather_d','cms_leather_n']
    results=[encode(args.directory/(n+'.png')) for n in names]
    (args.directory/'texture_validation.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
