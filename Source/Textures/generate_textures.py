"""Deterministic, correlated surface maps for forged iron, old wood and leather.

The PNGs use mesh UVs (V points up): image row increases opposite to V.
Normal RGB uses the same tangent basis as those UVs; alpha is Skyrim specular.
encode_dds converts the normal green channel for the NIF writer's flipped V.
Heights are authored in millimetres, not uncalibrated RGB noise. All material
layers wrap around U so the lathed handle and iron head have no cut seam.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree

N = 1024
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'build/textures/weapons/ChainMorningstarVR'
Y, X = np.mgrid[:N, :N].astype(np.float32)


def noise(rng, sigma):
    """Unit-range low-frequency field with real contrast at every scale."""
    a = gaussian_filter(rng.standard_normal((N, N)).astype(np.float32), sigma, mode='wrap')
    # Keep the same field contrast at large scales. Blurring 8-bit white noise
    # used to collapse nearly all broad material variation to a constant gray.
    return np.clip(.5 + a / max(float(a.std()) * 5, 1e-6), 0, 1)


def stamp(field, cx, cy, rx, ry, angle, depth, lip=None):
    """A locally stamped elliptical hammer blow; repeats across texture edges."""
    radius = int(math.ceil(max(rx, ry) * 2.5))
    yy, xx = np.mgrid[-radius:radius+1, -radius:radius+1].astype(np.float32)
    xx += math.floor(cx) - cx
    yy += math.floor(cy) - cy
    ca, sa = math.cos(angle), math.sin(angle)
    u, v = (xx*ca+yy*sa)/rx, (-xx*sa+yy*ca)/ry
    azimuth = np.arctan2(v,u)
    # Forging facets have irregular shoulders; perfect outlined ellipses read
    # as decorative bubbles rather than damaged metal.
    power = 2.6 if min(rx,ry)>3 else 2.0
    q = (np.abs(u)**power+np.abs(v)**power)**(2/power)
    q *= (1+.15*np.sin(3*azimuth+cx)+.08*np.sin(5*azimuth+cy))
    bowl = np.exp(-q * 1.8)
    # Slight raised rim is displaced material around a blow, not painted shine.
    rim = np.exp(-((np.sqrt(q)-1.03)/.21)**2)
    ix = (np.arange(-radius, radius+1) + math.floor(cx)) % N
    iy = (np.arange(-radius, radius+1) + math.floor(cy)) % N
    field[np.ix_(iy, ix)] += -depth*bowl + depth*.14*rim
    if lip is not None:
        lip[np.ix_(iy, ix)] = np.maximum(lip[np.ix_(iy, ix)], rim * np.maximum(np.cos(azimuth+angle),0)**3 * min(depth/2.2, 1))


def normal_from_height(h, uv_span_mm):
    """Central height derivative with unequal U/V physical texel dimensions."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * (N/(2*uv_span_mm[0]))
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * (N/(2*uv_span_mm[1]))
    n = np.stack([-dx, dy, np.ones_like(h)], axis=2)
    n /= np.linalg.norm(n, axis=2)[..., None]
    return np.rint((n*.5+.5)*255).clip(0,255).astype(np.uint8)


def save_material(out, name, diffuse, height, alpha, span, environment=None):
    diffuse = np.rint(diffuse).clip(0,255).astype(np.uint8)
    normals = normal_from_height(height, span)
    alpha = np.rint(alpha).clip(8,196).astype(np.uint8)
    Image.fromarray(diffuse).save(out/f'cms_{name}_d.png')
    Image.fromarray(np.dstack([normals, alpha])).save(out/f'cms_{name}_n.png')
    if environment is not None:
        Image.fromarray(np.rint(environment*255).clip(0,255).astype(np.uint8)).save(out/f'cms_{name}_m.png')
    n = normals.astype(np.float32)/127.5-1
    return dict(height_range_mm=[float(height.min()),float(height.max())],
                normal_mean_tilt_degrees=float(np.degrees(np.arccos(np.clip(n[:,:,2],-1,1))).mean()),
                normal_xy_rms=float(np.sqrt(np.mean(n[:,:,:2]**2))),
                diffuse_luma_std=float(diffuse.mean(2).std()),
                specular_range=[int(alpha.min()),int(alpha.max())],
                uv_span_mm=list(span))


def iron(out):
    rng = np.random.default_rng(2026100601)
    broad, scale, grit = noise(rng,36), noise(rng,7), noise(rng,.65)
    h = (broad-.5)*1.8 + (scale-.5)*.75 + (grit-.5)*.46
    lips = np.zeros((N,N),np.float32)
    # Large uneven forging marks must remain visible in a whole-weapon view.
    for _ in range(960):
        stamp(h,rng.uniform(0,N),rng.uniform(0,N),rng.uniform(7,26),rng.uniform(5,19),
              rng.uniform(0,math.tau),rng.uniform(.7,2.7),lips)
    # Corrosion pits and impact divots break the broad highlights at close range.
    for _ in range(2600):
        stamp(h,rng.uniform(0,N),rng.uniform(0,N),rng.uniform(.55,2.0),rng.uniform(.5,2.8),
              rng.uniform(0,math.tau),rng.uniform(.12,.65))
    for _ in range(135):
        stamp(h,rng.uniform(0,N),rng.uniform(0,N),rng.uniform(8,42),rng.uniform(.45,1.0),
              rng.uniform(0,math.tau),rng.uniform(.4,1.0),lips)
    cavity = np.clip((gaussian_filter(h,6,mode='wrap')-h)/1.9,0,1)
    patina = np.clip(.32+broad*.43+scale*.22,0,1)
    raised = np.clip((h-gaussian_filter(h,9,mode='wrap'))/.72,0,1)
    bare = np.clip(lips*.42 + raised*.32 + np.maximum(scale-.58,0)*.60,0,1)
    tone = 32 + 19*scale + 13*broad + 33*bare - 23*cavity
    diffuse = tone[...,None]*np.array([.98,1.0,1.025],np.float32)
    # Subtle warm oxide is visible only in recesses, with no orange-rust wash.
    diffuse += (cavity*patina)[...,None]*np.array([3.5,1,-1.8],np.float32)
    alpha = 39+126*bare+32*scale-29*cavity
    env = np.clip(.18+.57*bare+.12*scale-.17*cavity-.08*patina,.035,.86)
    return save_material(out,'metal',diffuse,h,alpha,(1080,570),env)


def wood(out):
    rng = np.random.default_rng(2026100602)
    broad = noise(rng,(45,12))
    grain = noise(rng,(49,3.6))
    # Grow uneven fibers around the two knots actually sculpted into the handle.
    warped_x = X + (noise(rng,(80,18))-.5)*22
    knot_specs = [(.25, .6875, 24,52),(.9125,.82143,21,45)]
    for u,v,rx,ry in knot_specs:
        dx = (X-u*N+N/2)%N-N/2
        dy = Y-(1-v)*N
        warped_x += np.sign(dx)*rx*.85*np.exp(-.5*((dx/(rx*2.6))**2+(dy/(ry*2))**2))
    grain = map_coordinates(grain,[Y,warped_x],order=1,mode='grid-wrap')
    coarse = map_coordinates(noise(rng,(24,8.0)),[Y,warped_x],order=1,mode='grid-wrap')
    h = (grain-.5)*.20+(coarse-.5)*1.9+(broad-.5)*.95
    fissures = np.zeros((N,N),np.float32)
    splinters = np.zeros((N,N),np.float32)
    # Interrupted, bending cracks; no globally repeated sinusoidal stripe.
    for _ in range(34):
        x0 = rng.uniform(0,N)
        mid = rng.uniform(0,N)
        length = rng.uniform(25,175)
        drift = np.interp(np.arange(N),np.linspace(0,N,17),rng.normal(0,6.0,17))
        dx = (warped_x - x0 - drift[:,None] + N/2)%N-N/2
        along = np.exp(-((Y-mid)/length)**6)
        width = rng.uniform(1.8,5.0)
        line = np.exp(-(dx/width)**2)*along
        fissures = np.maximum(fissures,line)
        edge = np.exp(-((dx-width*1.9)/(.7+width*.65))**2)*along
        splinters = np.maximum(splinters,edge)
        h -= line*rng.uniform(.65,2.2)
        h += edge*.16
    knot_dark = np.zeros((N,N),np.float32)
    for u,v,rx,ry in knot_specs:
        dx = (X-u*N+N/2)%N-N/2
        dy = Y-(1-v)*N
        r = np.sqrt((dx/rx)**2+(dy/ry)**2)
        core = np.exp(-(r/.60)**2)
        rings = (.5+.5*np.sin(r*18+(noise(rng,4)-.5)*3)) * np.exp(-(r/1.55)**4)
        knot_dark += core*.9+rings*.22
        h -= core*.75+rings*.34
    pores = (noise(rng,(5,1.1))-.5)*.055
    h += pores
    exposed = np.clip((coarse-.37)*1.4+splinters*.26,0,1)
    tone = 51+30*grain+24*coarse+13*broad-43*fissures-43*knot_dark+20*exposed
    diffuse = tone[...,None]*np.array([1.11,.89,.66],np.float32)
    # Worn raised fibers desaturate toward gray-beige, cracks stay dark brown.
    diffuse += exposed[...,None]*np.array([1.0,5.0,10.0],np.float32)
    diffuse *= (.89+.19*broad)[...,None]
    alpha = 19+28*exposed+11*grain-11*fissures
    return save_material(out,'wood',diffuse,h,alpha,(190,560))


def leather(out):
    rng = np.random.default_rng(2026100603)
    broad, mid, fine = noise(rng,40), noise(rng,7), noise(rng,.65)
    # Organic grain: nearest-seed cells give compressed valleys between raised
    # leather pebbles. Their random sizes avoid uniform gravel/noise rendering.
    seeds = rng.uniform(0,N,(13000,2))
    distances,_ = cKDTree(seeds,boxsize=N).query(np.column_stack([X.ravel(),Y.ravel()]),k=2)
    ridge_gap = (distances[:,1]-distances[:,0]).reshape(N,N).astype(np.float32)
    valleys = np.exp(-(ridge_gap/.62)**2)
    pebbles = np.clip(ridge_gap/2.5,0,1)
    h = .12*pebbles+(mid-.5)*.20+(broad-.5)*.48+(fine-.5)*.024
    folds = np.zeros((N,N),np.float32)
    fold_edge = np.zeros((N,N),np.float32)
    # Broken wrinkles from bending/compression under the user's hand.
    for _ in range(37):
        y0 = rng.uniform(0,N)
        center = rng.uniform(0,N)
        length = rng.uniform(40,200)
        waviness = np.interp(np.arange(N),np.linspace(0,N,33),rng.normal(0,8,33))
        line_y = y0+waviness[None,:]+(X-center)*rng.uniform(-.18,.18)
        dy = (Y-line_y+N/2)%N-N/2
        width = rng.uniform(1,4.5)
        along = np.exp(-(((X-center+N/2)%N-N/2)/length)**6)
        fold = np.exp(-(dy/width)**2)*along
        edge = np.exp(-((dy-width*1.7)/(width*.8+1))**2)*along
        folds = np.maximum(folds,fold)
        fold_edge = np.maximum(fold_edge,edge)
        h -= fold*rng.uniform(.12,.52)
        h += edge*.045
    scuff = np.clip((noise(rng,(5,12))-.65)*4.2,0,1)*(0.4+0.6*broad)
    # Dry fine cracks and pits live in worn patches, with burnished oily ridges
    # having higher specular than the fresh, fibrous tear surfaces.
    cracks = valleys*np.clip((mid-.48)*4,0,1)
    h -= cracks*.105
    polished = np.clip((broad-.28)*1.4+fold_edge*.28-scuff*.5,0,1)
    tone = 22+19*mid+11*broad+16*pebbles+38*scuff+17*fold_edge-23*folds-10*cracks
    diffuse = tone[...,None]*np.array([1.02,.76,.54],np.float32)
    diffuse += scuff[...,None]*np.array([6,5,3],np.float32)
    alpha = 24+81*polished-19*folds-23*scuff-12*cracks
    return save_material(out,'leather',diffuse,h,alpha,(185,255))


def generate(out=DEFAULT_OUT):
    out.mkdir(parents=True,exist_ok=True)
    metrics = {name:fn(out) for name,fn in [('metal',iron),('wood',wood),('leather',leather)]}
    report = dict(seed_version='20261006-material-revision-2',size=[N,N],
                  normal_png_convention='mesh tangent basis, original V up',
                  normal_dds_convention='NIF flipped V; green inverted during DDS encoding',
                  materials=metrics)
    (out/'material_generation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    generate(p.parse_args().out)
