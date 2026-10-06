"""Build game materials from the user's eight supplied surface images.

This is deterministic material conversion, not image synthesis. The supplied
colors and scratches remain authoritative. Technical operations are declared in
material_generation.json: UV crops, a narrow periodic seam feather, and bounded
height/specular estimates. Estimated normals are not measured PBR surface data.
PNG normals use original mesh V-up; encode_dds flips G once for NIF V-down.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

N = 1024
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[1] / 'build/textures/weapons/ChainMorningstarVR'
BASES = ['metal', 'wood', 'leather', 'cord', 'spike', 'chain', 'ring', 'emblem']
METALS = {'metal', 'spike', 'chain', 'ring', 'emblem'}
DARKEN = {'metal':.60, 'wood':.72, 'leather':.64, 'cord':.68,
          'spike':.66, 'chain':.62, 'ring':.66, 'emblem':.70}


def normal_from_height(h, uv_span_mm, wrap=(True, True)):
    """Central derivatives in physical millimetres, with explicit wrap axes."""
    h = np.asarray(h, np.float32)
    def derivative(axis, period):
        if period:
            return (np.roll(h, -1, axis) - np.roll(h, 1, axis)) * .5
        return np.gradient(h, axis=axis)
    dx = derivative(1, wrap[0]) * (h.shape[1] / uv_span_mm[0])
    dy = derivative(0, wrap[1]) * (h.shape[0] / uv_span_mm[1])
    n = np.stack([-dx, dy, np.ones_like(h)], axis=2)
    n /= np.linalg.norm(n, axis=2)[..., None]
    return np.rint((n*.5+.5)*255).clip(0,255).astype(np.uint8)


def feather_periodic(rgb, wrap, width=20):
    """Only reconcile narrow edge strips; preserve the interior source pixels."""
    a = np.array(rgb, dtype=np.float32, copy=True)
    for axis, enabled in [(1, wrap[0]), (0, wrap[1])]:
        if not enabled:
            continue
        view = np.moveaxis(a, axis, 0)
        for i in range(width):
            blend = .5 * (1 - i/(width-1))**2
            first, last = view[i].copy(), view[-1-i].copy()
            view[i] = first*(1-blend)+last*blend
            view[-1-i] = last*(1-blend)+first*blend
    return a


def load_source(name, manifest):
    record = manifest['materials'][name]
    path = HERE/record['source_file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['source_sha256']:
        raise ValueError(f'User source image hash mismatch: {path.name}')
    image = Image.open(path).convert('RGB')
    if image.size != (N, N):
        raise ValueError(f'Unexpected source size: {path.name}')
    return np.asarray(image, dtype=np.float32)


def material_pixels(name, source):
    """UV-space conversion; all crop coordinates refer to original 1254² PNG."""
    operation = {'source_color_scale': 1.0}
    if name == 'ring':
        # A complete broad decorative row, excluding the unrelated second row.
        box = [0, 138, 1254, 488]
        y0, y1 = round(box[1]*N/1254), round(box[3]*N/1254)
        im = Image.fromarray(source.astype(np.uint8)).crop((0, y0, N, y1))
        source = np.asarray(im.resize((N,N), Image.Resampling.LANCZOS), np.float32)
        operation.update(crop_original_pixels=box, uv='U follows collar circumference; V follows collar height')
    elif name == 'cord':
        # Sample just the interior of one actual raised strap, between crossings.
        # Using the full photograph would paint extra crossed straps on each
        # existing 3D lace. U goes across the strap; V goes along its length.
        p0, p1 = np.array([345., 296.]), np.array([565., 216.])
        direction = p1-p0
        across = np.array([-direction[1],direction[0]])/np.linalg.norm(direction)
        yy,xx = np.mgrid[:N,:N].astype(np.float32)
        points = p0+(yy[...,None]/(N-1))*direction+((xx[...,None]/(N-1))-.5)*10*across
        points *= (N-1)/1253
        source = np.stack([map_coordinates(source[:,:,c],[points[:,:,1],points[:,:,0]],order=1,mode='nearest') for c in range(3)],axis=2)
        operation.update(strip_original_pixels={'start':p0.tolist(),'end':p1.tolist(),'width':10}, uv='U across clean strap face; V along lace; source crossings excluded')
    wrap = (False,False) if name=='emblem' else (True,False) if name in {'wood','spike','ring'} else (True,True)
    source = feather_periodic(source, wrap)
    operation.update(periodic_axes_uv=list(wrap),seam_feather_pixels=20 if any(wrap) else 0)
    if name == 'spike':
        # UV V=1 is the physical tip. Keep the source hammer marks and add a
        # restrained silver wear lift only to the last 16% of the cone.
        v = 1-np.arange(N,dtype=np.float32)/(N-1)
        lift = np.clip((v-.84)/.16,0,1)**1.8
        source = source*(1-lift[:,None,None]*.22)+np.array([202,204,206],np.float32)*lift[:,None,None]*.22
        operation['tip_wear']={'starts_at_v':.84,'maximum_silver_blend':.22,'tip_color':[202,204,206]}
    return np.rint(source).clip(0,255).astype(np.uint8), wrap, operation


def derive_maps(name, rgb, wrap):
    luma = rgb.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32)/255
    modes = ('wrap' if wrap[1] else 'reflect','wrap' if wrap[0] else 'reflect')
    # The photographs already contain lighting. Remove broad illumination from
    # inferred height, and bound depth instead of turning every dark area into
    # a deep hole. The emblem geometry owns all >=3px broad relief frequencies.
    sigma = 3.0 if name=='emblem' else 12.0
    detail = gaussian_filter(luma,1.15,mode=modes)-gaussian_filter(luma,sigma,mode=modes)
    depth = {'metal':1.15,'wood':.65,'leather':.26,'cord':.035,'spike':.32,'chain':.18,'ring':.24,'emblem':.17}[name]
    height = np.clip(detail*depth*3,-depth/2,depth/2)
    span = {'metal':(1080,570),'wood':(190,560),'leather':(185,255),'cord':(10.4,270),'spike':(190,86),'chain':(66,100),'ring':(270,50),'emblem':(269.10067114,269.10067114)}[name]
    normal = normal_from_height(height,span,wrap)
    lum = np.clip(gaussian_filter(luma,1,mode=modes),0,1)
    if name in METALS:
        # Bright worn edges reflect more; black recesses stay matte. Conservative
        # scales prevent supplied highlight colors from being blown out twice.
        alpha = 20+132*np.clip((lum-.035)/.78,0,1)
        environment = .035+.34*np.clip((lum-.035)/.78,0,1)
    else:
        base,strength={'wood':(14,29),'leather':(16,36),'cord':(18,47)}[name]
        alpha=base+strength*lum
        environment=None
    return height,normal,np.rint(alpha).clip(8,196).astype(np.uint8),span,environment


def save_png_atomic(image,path):
    pending=path.with_suffix('.pending.png')
    image.save(pending)
    pending.replace(path)


def darken_diffuse(name, rgb):
    """Lower albedo after height extraction; retain source grain and worn tips.

    A small luminance-dependent lift keeps the brightest wear legible against
    the black iron. No blur, gamma clipping, or changes to the normal field.
    """
    pixels = rgb.astype(np.float32)
    luma = pixels @ np.array([.2126,.7152,.0722],np.float32) / 255
    lift = .08 * np.clip((luma-.45)/.55,0,1) if name in METALS else 0
    factor = DARKEN[name] + lift
    if isinstance(factor,np.ndarray): factor = factor[...,None]
    return np.rint(pixels * factor).clip(0,255).astype(np.uint8)


def generate(out=DEFAULT_OUT):
    out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((HERE/'source_manifest.json').read_text(encoding='utf-8'))
    metrics={}
    for name in BASES:
        source=load_source(name,manifest)
        rgb,wrap,operations=material_pixels(name,source)
        height,normal,alpha,span,environment=derive_maps(name,rgb,wrap)
        if name=='emblem':
            # Mesh relief must keep its approved displacement when albedo is
            # darkened. This build-only image is never shipped as a game map.
            save_png_atomic(Image.fromarray(rgb),out/'cms_emblem_relief_source.png')
        # Crucially, derive relief from the approved source colors first.
        # The darker finish must not flatten leather dents or hammered iron.
        before_luma=float((rgb.astype(np.float32)@np.array([.2126,.7152,.0722])).mean())
        rgb=darken_diffuse(name,rgb)
        operations.update(source_color_scale=DARKEN[name],
                          bright_wear_scale_lift=.08 if name in METALS else 0,
                          normal_height_source='approved source before darkening')
        save_png_atomic(Image.fromarray(rgb),out/f'cms_{name}_d.png')
        save_png_atomic(Image.fromarray(np.dstack([normal,alpha])),out/f'cms_{name}_n.png')
        if environment is not None:
            save_png_atomic(Image.fromarray(np.rint(environment*255).clip(0,255).astype(np.uint8)),out/f'cms_{name}_m.png')
        n=normal.astype(np.float32)/127.5-1
        metrics[name]={
            'source':manifest['materials'][name], 'operations':operations,
            'height_estimation':'bounded high-pass luminance, not measured displacement',
            'height_range_mm':[float(height.min()),float(height.max())],
            'normal_mean_tilt_degrees':float(np.degrees(np.arccos(np.clip(n[:,:,2],-1,1))).mean()),
            'normal_xy_rms':float(np.sqrt(np.mean(n[:,:,:2]**2))),
            'diffuse_luma_std':float(rgb.mean(2).std()),
            'diffuse_luma_mean_before':before_luma,
            'diffuse_luma_mean_after':float((rgb.astype(np.float32)@np.array([.2126,.7152,.0722])).mean()),
            'specular_range':[int(alpha.min()),int(alpha.max())],
            'uv_span_mm':list(span),'environment_map':environment is not None}
    report={'schema_version':3,'material_revision':'20261006-black-iron-070', 'size':[N,N],
            'source_archive_sha256':manifest['archive_sha256'],
            'normal_png_convention':'mesh tangent basis, original V up',
            'normal_dds_convention':'NIF flipped V; green inverted during DDS encoding',
            'materials':metrics,
            'dds_files':[f'cms_{name}_{kind}.dds' for name in BASES for kind in ('d','n','m') if kind!='m' or name in METALS]}
    (out/'material_generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in m.items() if k in {'height_range_mm','specular_range','normal_mean_tilt_degrees'}} for name,m in metrics.items()},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    generate(p.parse_args().out)
