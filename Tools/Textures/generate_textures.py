#!/usr/bin/env python3
"""Deterministic clean-room texture generator for ChainMorningstarVR.

Generates project-owned forged-steel, wood and leather DDS textures.
No Bethesda or third-party game texture is copied or sampled.
DDS output is BC3/BC5 with a full mip chain.
"""
from __future__ import annotations

import io
import math
import os
import struct
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 1024
SEED = 0x434D5356
OUT_NAMES = {
    "cms_metal_d.dds": "BC3",
    "cms_metal_n.dds": "BC5",
    "cms_metal_m.dds": "BC3",
    "cms_wood_d.dds": "BC3",
    "cms_wood_n.dds": "BC5",
    "cms_leather_d.dds": "BC3",
    "cms_leather_n.dds": "BC5",
}

DDSD_MIPMAPCOUNT = 0x00020000
DDSCAPS_COMPLEX = 0x00000008
DDSCAPS_MIPMAP = 0x00400000
DXGI_BC3_UNORM = 76
DXGI_BC5_UNORM = 82


def normalize01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-8:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


def smooth_noise(rng: np.random.Generator, size: int, grid: int) -> np.ndarray:
    small = rng.normal(0.0, 1.0, (grid, grid)).astype(np.float32)
    im = Image.fromarray(small, mode="F").resize((size, size), Image.Resampling.BICUBIC)
    return np.asarray(im, dtype=np.float32)


def multiscale_noise(rng: np.random.Generator, size: int) -> np.ndarray:
    out = np.zeros((size, size), np.float32)
    for grid, amp in ((8, 1.0), (20, 0.55), (48, 0.28), (128, 0.13)):
        out += smooth_noise(rng, size, grid) * amp
    return normalize01(out)


def normals_from_height(height: np.ndarray, strength: float) -> np.ndarray:
    gy, gx = np.gradient(height.astype(np.float32))
    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(nx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack((nx * inv, ny * inv, nz * inv), axis=2)
    return np.clip((n * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def rgba(rgb: np.ndarray, alpha: int = 255) -> Image.Image:
    a = np.full((*rgb.shape[:2], 1), alpha, np.uint8)
    return Image.fromarray(np.concatenate((rgb.astype(np.uint8), a), axis=2), "RGBA")


def metal_textures(rng: np.random.Generator):
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n = multiscale_noise(rng, SIZE)
    fine = rng.normal(0.0, 1.0, (SIZE, SIZE)).astype(np.float32)

    angle = math.radians(17.0)
    axis = x * math.cos(angle) + y * math.sin(angle)
    brushed = np.sin(axis * 0.19 + smooth_noise(rng, SIZE, 28) * 2.4)
    scars = np.zeros((SIZE, SIZE), np.float32)
    for _ in range(34):
        cx = rng.uniform(0, SIZE)
        cy = rng.uniform(0, SIZE)
        a = rng.uniform(-0.45, 0.45)
        length = rng.uniform(90, 360)
        width = rng.uniform(0.8, 2.5)
        dx, dy = math.cos(a), math.sin(a)
        px = (x - cx) * dx + (y - cy) * dy
        py = -(x - cx) * dy + (y - cy) * dx
        scars -= np.exp(-0.5 * (py / width) ** 2) * np.exp(-0.5 * (px / length) ** 8)

    height = 0.42 * n + 0.035 * brushed + 0.018 * fine + 0.12 * scars
    tone = np.clip(0.30 + 0.30 * n + 0.035 * brushed + 0.04 * fine + 0.10 * scars, 0, 1)
    base = np.stack((tone * 168, tone * 176, tone * 184), axis=2)
    base = np.clip(base, 22, 190).astype(np.uint8)
    normal = normals_from_height(height, 11.0)

    mask = np.clip(0.42 + 0.30 * n + 0.08 * brushed + 0.25 * scars, 0.06, 0.88)
    m = (mask * 255.0).astype(np.uint8)
    mask_rgb = np.stack((m, m, m), axis=2)
    return rgba(base), Image.fromarray(normal, "RGB"), rgba(mask_rgb)


def wood_textures(rng: np.random.Generator):
    y, _x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    warp = smooth_noise(rng, SIZE, 22) * 34.0 + smooth_noise(rng, SIZE, 65) * 8.0
    grain_phase = (y + warp) * 0.052
    grain = 0.55 * np.sin(grain_phase) + 0.25 * np.sin(grain_phase * 2.31 + 0.8)
    pores = multiscale_noise(rng, SIZE)
    height = grain * 0.13 + pores * 0.20
    tone = np.clip(0.34 + 0.14 * grain + 0.24 * pores, 0, 1)
    rgb = np.stack((tone * 111, tone * 62, tone * 31), axis=2)
    rgb = np.clip(rgb, 18, 124).astype(np.uint8)
    return rgba(rgb), Image.fromarray(normals_from_height(height, 7.0), "RGB")


def leather_textures(rng: np.random.Generator):
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    low = multiscale_noise(rng, SIZE)
    pebble = np.sin(x * 0.17 + low * 5.0) * np.sin(y * 0.15 - low * 4.0)
    pores = rng.normal(0.0, 1.0, (SIZE, SIZE)).astype(np.float32)
    height = 0.17 * pebble + 0.08 * low + 0.018 * pores
    tone = np.clip(0.22 + 0.10 * pebble + 0.17 * low + 0.018 * pores, 0, 1)
    rgb = np.stack((tone * 92, tone * 51, tone * 34), axis=2)
    rgb = np.clip(rgb, 12, 96).astype(np.uint8)
    return rgba(rgb), Image.fromarray(normals_from_height(height, 8.0), "RGB")


def single_level_dds(img: Image.Image, fmt: str) -> tuple[bytearray, bytes]:
    buf = io.BytesIO()
    src = img.convert("RGB") if fmt == "BC5" else img.convert("RGBA")
    src.save(buf, format="DDS", pixel_format=fmt)
    data = buf.getvalue()
    if data[:4] != b"DDS ":
        raise RuntimeError("Pillow did not emit a DDS header")
    header_size = 148 if data[84:88] == b"DX10" else 128
    if header_size != 148:
        raise RuntimeError("DX10 DDS header required")
    return bytearray(data[:header_size]), data[header_size:]


def write_mipped_dds(img: Image.Image, path: Path, fmt: str) -> None:
    levels: list[bytes] = []
    cur = img
    top_header: bytearray | None = None
    while True:
        header, payload = single_level_dds(cur, fmt)
        if top_header is None:
            top_header = header
        levels.append(payload)
        if cur.width == 1 and cur.height == 1:
            break
        cur = cur.resize((max(1, cur.width // 2), max(1, cur.height // 2)), Image.Resampling.LANCZOS)

    assert top_header is not None
    flags = struct.unpack_from("<I", top_header, 8)[0] | DDSD_MIPMAPCOUNT
    struct.pack_into("<I", top_header, 8, flags)
    struct.pack_into("<I", top_header, 28, len(levels))
    caps = struct.unpack_from("<I", top_header, 108)[0] | DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    struct.pack_into("<I", top_header, 108, caps)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(top_header)
        for payload in levels:
            f.write(payload)


def validate_dds(path: Path, expected_fmt: str) -> None:
    data = path.read_bytes()
    if data[:4] != b"DDS " or len(data) < 160:
        raise RuntimeError(f"{path.name}: invalid DDS")
    width = struct.unpack_from("<I", data, 16)[0]
    height = struct.unpack_from("<I", data, 12)[0]
    mip_count = struct.unpack_from("<I", data, 28)[0]
    fourcc = data[84:88]
    dxgi = struct.unpack_from("<I", data, 128)[0] if fourcc == b"DX10" else -1
    expected_dxgi = DXGI_BC5_UNORM if expected_fmt == "BC5" else DXGI_BC3_UNORM
    if (width, height) != (SIZE, SIZE):
        raise RuntimeError(f"{path.name}: expected {SIZE}x{SIZE}, got {width}x{height}")
    if mip_count != int(math.log2(SIZE)) + 1:
        raise RuntimeError(f"{path.name}: incomplete mip chain ({mip_count})")
    if fourcc != b"DX10" or dxgi != expected_dxgi:
        raise RuntimeError(f"{path.name}: expected {expected_fmt}/DXGI {expected_dxgi}, got {fourcc!r}/{dxgi}")
    with Image.open(path) as im:
        im.load()
        if im.size != (SIZE, SIZE):
            raise RuntimeError(f"{path.name}: Pillow round-trip size mismatch")


def main() -> None:
    out = Path(os.environ.get("CMS_TEXTURE_OUT", "texture-artifact/textures/weapons/ChainMorningstarVR"))
    rng = np.random.default_rng(SEED)
    metal_d, metal_n, metal_m = metal_textures(rng)
    wood_d, wood_n = wood_textures(rng)
    leather_d, leather_n = leather_textures(rng)

    images = {
        "cms_metal_d.dds": metal_d,
        "cms_metal_n.dds": metal_n,
        "cms_metal_m.dds": metal_m,
        "cms_wood_d.dds": wood_d,
        "cms_wood_n.dds": wood_n,
        "cms_leather_d.dds": leather_d,
        "cms_leather_n.dds": leather_n,
    }

    for name, img in images.items():
        fmt = OUT_NAMES[name]
        path = out / name
        write_mipped_dds(img, path, fmt)
        validate_dds(path, fmt)
        print(f"CMS_TEXTURE_VALIDATE: PASS {name} {fmt} {SIZE}x{SIZE} full-mips bytes={path.stat().st_size}")


if __name__ == "__main__":
    main()
