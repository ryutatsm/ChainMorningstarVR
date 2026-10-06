# Reference mesh build

The current asset source is `generate_reference_mesh.py` plus
`export_reference_nif.cpp`. The former Blender/PyNifly primitive generator has
been retired. CI must never build that previous appearance.

The supplied reference image was inspected directly. This model is generated
from numeric geometry, with no older weapon NIF or texture as a template.
The real NIF, GLB and mesh renders come from the same vertices and node hierarchy.

## Reproduction

Python 3.12 and the pinned packages in `requirements-assets.txt` are required.
The portable writer uses **ousnius/nifly** commit
`cca0a770094bb962fb28ea1fec5ea903e68fda8e`:
https://github.com/ousnius/nifly/tree/cca0a770094bb962fb28ea1fec5ea903e68fda8e

nifly is a third-party NIF parser/writer under GPLv3. Its source files and license
are in that pinned upstream tree. No old weapon project code is used by this
writer. The local dependency source archive's GitHub ZIP comment identifies
that revision; its original `nifly-main.zip` SHA-256 was
`a15549d6758ad1ed746c7bb6e1b7619146a14410206197e4214841496df39691`.
The archive hash is provenance, not the hash of a differently named commit ZIP.

From the repository root, with `NIFLY_SOURCE` the local source directory:

```sh
python -m pip install -r Source/NIF/requirements-assets.txt
cmake -S Source/NIF -B build/asset-exporter -DCMS_NIFLY_ROOT="$NIFLY_SOURCE"
cmake --build build/asset-exporter --config Release --parallel 2
python Source/Textures/generate_textures.py
python Source/Textures/encode_dds.py build/textures/weapons/ChainMorningstarVR
python Source/NIF/generate_reference_mesh.py --out build/visual-preview --textures build/textures/weapons/ChainMorningstarVR
python Source/NIF/validate_reference_assets.py --build build
mkdir -p build/meshes/weapons/ChainMorningstarVR
build/asset-exporter/export_reference_nif build/visual-preview/reference_mesh.cms build/meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif
```

On Windows the executable is `build/asset-exporter/Release/export_reference_nif.exe`.
`windows-nif-build.yml` performs this entire pipeline. DDS texture generation is
also independently gated by `windows-texture-build.yml`.

Optional CPU preview (uses DejaVu Sans on Linux):

```sh
python Source/NIF/render_reference_mesh.py --textures build/textures/weapons/ChainMorningstarVR --out build/visual-preview
```

## Retained contracts and changes

- Root +Y remains the handle axis. Anchor local +Z maps to root +Y.
- Handle: 56 cm, origin in the leather grip; anchor at root Y = 40 cm.
- 14 alternating oval links, 84 cm first-to-last centre span.
- Head centre: 106.5 cm from anchor; 16 cm core radius, 24 cm spike-tip radius.
- Eight rim spikes are rotated 22.5 degrees to leave the chain socket clear.
  Six remaining spikes sit at local Y = +/-0.64 times their axis distance.
  The exact 14 directions also live in `HeadCompoundCore.hpp`.
- The NIF still has `CMS_ChainAnchor`, `CMS_LinkNode_00` to `13`, `CMS_HeadNode`.
- Head collision: 15 convex pieces (core + 14 spikes), heavy-metal material,
  8 kg authored rigid body. Socket/eyelets/decoration do not add damage hulls.
- Tapered wood, crossed leather cords, engraved collars, open pommel ring,
  modelled head socket, diamond plaque and filled dragon relief replace the
  previous plain cylinders, spherical pommel and plain sphere.
- Seven authored 1024 x 1024 DXT5 textures each have all 11 mip levels.
  Normal RGB is renormalized at every mip; alpha stores material specular.

## Verification and limits

The geometry validator checks emitted triangle winding, unit normals, index
bounds, exact node transforms, alternating links, hull half-spaces and spike
positions. It confirms GLB vertex/normal/UV bytes match the NIF writer input.
The NIF writer saves and reloads the output with nifly and checks the compound
collision and hierarchy. DDS validation decodes all 77 mip levels.

These are development assets. A NIF parser round-trip cannot prove that Skyrim
VR instantiates the Havok body correctly, that its collision follows the
runtime solver, or that the weapon deals native melee damage.

The front reference does not specify the back and underside. The dragon relief
and metal engravings are modelled interpretations, not an exact surface scan.
Collar ornament, spike profile and etched surface details are still less rich
than the supplied reference. The previews use a software material illustration;
the actual game's lighting, mip bias and environment shader remain unverified.
The GLB uses simplified PBR materials and is intended for geometry inspection.
