#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import math
import struct
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()

REQUIRED = {
    "ChainMorningstarVR.esp",
    "SKSE/Plugins/ChainMorningstarVR.dll",
    "meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif",
    "textures/weapons/ChainMorningstarVR/cms_metal_d.dds",
    "textures/weapons/ChainMorningstarVR/cms_metal_n.dds",
    "textures/weapons/ChainMorningstarVR/cms_metal_m.dds",
    "textures/weapons/ChainMorningstarVR/cms_wood_d.dds",
    "textures/weapons/ChainMorningstarVR/cms_wood_n.dds",
    "textures/weapons/ChainMorningstarVR/cms_leather_d.dds",
    "textures/weapons/ChainMorningstarVR/cms_leather_n.dds",
    "README_DIAGNOSTIC.txt",
}

DDS_EXPECTED = {
    "cms_metal_d.dds": 76,   # BC3_UNORM
    "cms_metal_n.dds": 82,   # BC5_UNORM
    "cms_metal_m.dds": 76,
    "cms_wood_d.dds": 76,
    "cms_wood_n.dds": 82,
    "cms_leather_d.dds": 76,
    "cms_leather_n.dds": 82,
}


def rels() -> set[str]:
    return {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file()
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_dds(path: Path, dxgi_expected: int) -> None:
    b = path.read_bytes()
    if len(b) < 148 or b[:4] != b"DDS ":
        raise RuntimeError(f"{path.name}: invalid DDS")
    height = struct.unpack_from("<I", b, 12)[0]
    width = struct.unpack_from("<I", b, 16)[0]
    mip_count = struct.unpack_from("<I", b, 28)[0]
    fourcc = b[84:88]
    dxgi = struct.unpack_from("<I", b, 128)[0] if fourcc == b"DX10" else -1
    if (width, height) != (1024, 1024):
        raise RuntimeError(f"{path.name}: expected 1024x1024, got {width}x{height}")
    if mip_count != int(math.log2(1024)) + 1:
        raise RuntimeError(f"{path.name}: expected full 11 mip levels, got {mip_count}")
    if fourcc != b"DX10" or dxgi != dxgi_expected:
        raise RuntimeError(f"{path.name}: unexpected DDS format {fourcc!r}/DXGI {dxgi}")


def main() -> None:
    found = rels()
    missing = REQUIRED - found
    if missing:
        raise RuntimeError(f"Missing required package files: {sorted(missing)}")

    forbidden_fragments = (
        "native-proxy-test",
        "ChainedMorningstar",
        "Animated chains",
        "Animated chains reupload",
    )
    for r in found:
        low = r.lower()
        for frag in forbidden_fragments:
            if frag.lower() in low:
                raise RuntimeError(f"Forbidden/legacy path leaked into package: {r}")

    esp = ROOT / "ChainMorningstarVR.esp"
    dll = ROOT / "SKSE/Plugins/ChainMorningstarVR.dll"
    nif = ROOT / "meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif"

    if esp.read_bytes()[:4] != b"TES4":
        raise RuntimeError("ESP does not begin with TES4 record signature")
    if dll.read_bytes()[:2] != b"MZ":
        raise RuntimeError("DLL does not have a PE/MZ header")
    if nif.stat().st_size < 100_000:
        raise RuntimeError("NIF unexpectedly small")

    dll_bytes = dll.read_bytes()
    required_dll_strings = (
        b"0.4.3-dev",
        b"READ-ONLY MOTION",
        b"PHYChainSD",
        b"PHYGenericMetalHeavyH",
    )
    for s in required_dll_strings:
        if s not in dll_bytes:
            raise RuntimeError(f"Diagnostic DLL missing expected marker: {s!r}")

    forbidden_dll_strings = (
        b"native melee proxy installed",
        b"collisionNode -> CMS_HeadNode",
    )
    for s in forbidden_dll_strings:
        if s in dll_bytes:
            raise RuntimeError(f"Write-enabled native proxy marker found in diagnostic DLL: {s!r}")

    tex_dir = ROOT / "textures/weapons/ChainMorningstarVR"
    for name, dxgi in DDS_EXPECTED.items():
        validate_dds(tex_dir / name, dxgi)

    readme = (ROOT / "README_DIAGNOSTIC.txt").read_text(encoding="utf-8")
    for marker in (
        "READ-ONLY",
        "NOT A FINAL RELEASE",
        "CMS_ENABLE_NATIVE_MELEE_PROXY=OFF",
        "PHYChainSD",
    ):
        if marker not in readme:
            raise RuntimeError(f"README missing safety marker: {marker}")

    manifest = ROOT / "SHA256SUMS.txt"
    lines = []
    for p in sorted((p for p in ROOT.rglob("*") if p.is_file() and p.name != manifest.name),
                    key=lambda p: p.relative_to(ROOT).as_posix().lower()):
        lines.append(f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("CMS_PACKAGE_VALIDATE: PASS")
    print(f"CMS_PACKAGE_FILES: {len(found)} required-present")
    print(f"CMS_PACKAGE_ESP_SHA256: {sha256(esp)}")
    print(f"CMS_PACKAGE_DLL_SHA256: {sha256(dll)}")
    print(f"CMS_PACKAGE_NIF_SHA256: {sha256(nif)}")


if __name__ == "__main__":
    main()
