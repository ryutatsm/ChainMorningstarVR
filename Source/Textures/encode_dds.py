"""Encode supplied-material Skyrim BC3/DXT5 textures, decode and validate all 11 mips.

Canonical PNG normal maps follow the source mesh's V-up tangent basis. The NIF
writer flips V before it builds its tangent basis, so this encoder flips normal
G exactly once. Specular alpha is retained independently of the normal vectors.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

BASES = ['metal','wood','leather','cord','spike','chain','ring','emblem']
METALS = {'metal','spike','chain','ring','emblem'}
NAMES = [f'cms_{base}_{kind}' for base in BASES for kind in ('d','n','m')
         if kind != 'm' or base in METALS]


def encode_bc3_alpha(pixels, blocks):
    """Use actual BC3 alpha endpoints and nearest palette indices.

    Pillow's current DXT5 encoder chooses interpolated alpha codes even for
    exact endpoints (e.g. input 16/180 decodes as 48/147). Since this channel is
    material specular, preserve endpoints and quantize its 16 samples directly.
    RGB still uses Pillow's compressor; the eight alpha bytes are independent.
    """
    h,w=pixels.shape
    padded=np.pad(pixels,((0,(-h)%4),(0,(-w)%4)),mode='edge')
    samples=padded.reshape(padded.shape[0]//4,4,padded.shape[1]//4,4).transpose(0,2,1,3).reshape(-1,16).astype(np.int16)
    hi=samples.max(1);lo=samples.min(1)
    palette=np.empty((len(samples),8),np.int16);palette[:,0]=hi;palette[:,1]=lo
    for i in range(2,8):
        palette[:,i]=((8-i)*hi+(i-1)*lo)//7
    # Equal endpoints use the alternate six-alpha mode. Every sample is exactly
    # that endpoint and therefore selects code zero; unused palette is harmless.
    indices=np.abs(samples[:,:,None]-palette[:,None,:]).argmin(2).astype(np.uint64)
    packed=np.zeros(len(samples),np.uint64)
    for i in range(16):
        packed |= indices[:,i] << np.uint64(i*3)
    result=np.frombuffer(blocks,dtype=np.uint8).copy().reshape(-1,16)
    result[:,0]=hi;result[:,1]=lo
    for i in range(6):
        result[:,2+i]=((packed >> np.uint64(i*8)) & np.uint64(255)).astype(np.uint8)
    return result.tobytes()


def encode(src: Path):
    im = Image.open(src).convert('RGBA')
    normal = src.stem.endswith('_n')
    if im.size != (1024,1024):
        raise ValueError('Expected 1024 x 1024')
    if normal:
        pixels = np.asarray(im).copy()
        pixels[:,:,1] = 255-pixels[:,:,1]  # NIF writer uses V'=1-V.
        im = Image.fromarray(pixels)
    levels = []
    width,height = im.size
    while True:
        if normal:
            data = np.asarray(im).copy()
            n = data[:,:,:3].astype(np.float32)/127.5-1
            n /= np.maximum(np.linalg.norm(n,axis=2)[:,:,None],1e-9)
            data[:,:,:3] = np.rint((n*.5+.5)*255).clip(0,255).astype('uint8')
            im = Image.fromarray(data)
        b = io.BytesIO()
        im.save(b,format='DDS',pixel_format='DXT5')
        raw = b.getvalue()
        source_pixels=np.asarray(im)
        payload=encode_bc3_alpha(source_pixels[:,:,3],raw[128:])
        levels.append((im.size,payload,source_pixels))
        if im.size == (1,1):
            header = bytearray(raw[:128])
            break
        next_size = (max(1,im.width//2),max(1,im.height//2))
        if normal:
            # Pillow's RGBA resampling premultiplies RGB by alpha. Here alpha
            # is specular, not coverage: filtering it together would bend the
            # normals toward glossy pixels and can invent zero-alpha ringing.
            im = Image.merge('RGBA',tuple(channel.resize(next_size,Image.Resampling.BOX) for channel in im.split()))
        else:
            im = im.resize(next_size,Image.Resampling.LANCZOS)
    struct.pack_into('<I',header,8,0xA1007)
    struct.pack_into('<I',header,12,height)
    struct.pack_into('<I',header,16,width)
    struct.pack_into('<I',header,20,len(levels[0][1]))
    struct.pack_into('<I',header,28,len(levels))
    struct.pack_into('<I',header,108,0x401008)
    dst = src.with_suffix('.dds')
    dst.write_bytes(header+b''.join(data for _,data,_ in levels))
    offset = 128
    mip_checks = []
    alpha_range = None
    for i,((w,h),data,source_pixels) in enumerate(levels):
        expected_bytes = max(1,(w+3)//4)*max(1,(h+3)//4)*16
        assert len(data) == expected_bytes
        mh = bytearray(header)
        struct.pack_into('<I',mh,12,h)
        struct.pack_into('<I',mh,16,w)
        struct.pack_into('<I',mh,20,len(data))
        struct.pack_into('<I',mh,28,1)
        struct.pack_into('<I',mh,108,0x1000)
        decoded = Image.open(io.BytesIO(mh+data)).convert('RGBA')
        assert decoded.size == (w,h)
        check = dict(level=i,size=[w,h],bytes=len(data))
        if normal:
            decoded_pixels = np.asarray(decoded)
            alpha = decoded_pixels[:,:,3]
            rgb = decoded_pixels[:,:,:3]
            assert int(alpha.max()) < 200 and int(alpha.min()) > 0, 'Normal alpha lost specular range'
            assert float(rgb[:,:,2].mean()) > 210, 'Unexpected normal direction'
            original = source_pixels[:,:,:3].astype(np.float32)/127.5-1
            actual = rgb.astype(np.float32)/127.5-1
            original /= np.maximum(np.linalg.norm(original,axis=2)[:,:,None],1e-9)
            actual /= np.maximum(np.linalg.norm(actual,axis=2)[:,:,None],1e-9)
            angular_error = np.degrees(np.arccos(np.clip(np.sum(original*actual,axis=2),-1,1)))
            alpha_rmse = float(np.sqrt(np.mean((alpha.astype(np.float32)-source_pixels[:,:,3])**2)))
            mean_error = float(angular_error.mean())
            # Error compares the decoded mip to its authored, normalized mip.
            # This catches broken/swizzled channels instead of merely file size.
            assert mean_error < 12.0, f'Excessive BC3 normal direction error: {src.name} mip {i}: {mean_error:.3f}'
            assert alpha_rmse < 4.0, f'Specular alpha corrupted: {src.name} mip {i} RMSE {alpha_rmse:.3f}'
            check.update(normal_mean_error_degrees=mean_error,
                         specular_alpha_rmse=alpha_rmse,
                         specular_alpha_range=[int(alpha.min()),int(alpha.max())])
            if i==0:
                alpha_range = check['specular_alpha_range']
        mip_checks.append(check)
        offset += len(data)
    assert offset == dst.stat().st_size and len(levels) == 11
    return dict(name=dst.name,bytes=dst.stat().st_size,format='DXT5',
                size=[1024,1024],mip_levels=11,decoded_mips=11,
                normal_green_inverted_for_nif=normal,
                normal_specular_alpha_range=alpha_range,mip_checks=mip_checks,
                sha256=hashlib.sha256(dst.read_bytes()).hexdigest())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    results=[encode(args.directory/(n+'.png')) for n in NAMES]
    (args.directory/'texture_validation.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps([dict(name=r['name'],decoded_mips=r['decoded_mips'],
                           specular_range=r['normal_specular_alpha_range'],
                           worst_mip_normal_error_degrees=max((m.get('normal_mean_error_degrees',0) for m in r['mip_checks']))) for r in results],indent=2))
