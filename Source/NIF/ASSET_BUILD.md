# Reference mesh build

The current asset source is `generate_reference_mesh.py` plus
`export_reference_nif.cpp`. The former Blender/PyNifly primitive generator has
been retired. CI must never build that previous appearance.

The supplied reference images were inspected directly. This model is generated
from numeric geometry and the user-provided material images, with no older
weapon NIF or texture as a template.
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
- Handle: 42 cm, origin in the leather grip; anchor at root Y = 30 cm.
- 19 alternating oval links, 87.23077 cm first-to-last centre span.
  All dimensions are 75% of the approved model, with five extra scaled links.
  `Source/SKSE/WeaponDimensions.hpp` is read by both asset generation and runtime.
- Head centre: 104.10577 cm from anchor; 12 cm core radius, 18 cm spike-tip radius.
- Eight rim spikes are rotated 22.5 degrees to leave the chain socket clear.
  Six remaining spikes sit at local Y = +/-0.64 times their axis distance.
  The exact 14 directions also live in `HeadCompoundCore.hpp`.
- The NIF still has `CMS_ChainAnchor`, `CMS_LinkNode_00` to `18`, `CMS_HeadNode`.
- Head collision: 15 convex pieces (core + 14 spikes), heavy-metal material,
  12 kg authored rigid body. Socket/eyelets/decoration do not add damage hulls.
- Tapered wood, crossed leather cords, engraved collars, open pommel ring,
  modelled head socket, curved diamond plaque and image-derived relief replace the
  previous plain cylinders, spherical pommel and plain sphere.
- Twenty-one 1024 x 1024 DXT5 textures each have all 11 mip levels. Eight
  materials have diffuse/normal maps; the five metals also have environment masks.
  Normal RGB is renormalized at every mip; alpha stores material specular.

BloodFX and BloodLighting are generated from the actual core, spike and emblem
surfaces, offset 0.225 mm along their normals and parented to CMS_HeadNode.
Both start hidden and use the vanilla iron mace shader/alpha contract; native
weapon-blood processing owns display and fading. The standard three blood DDS
paths and EyeCubeMap are referenced from Skyrim, not redistributed. The GLB
preview omits these initially hidden NIF-only passes.

## Verification and limits

The geometry validator checks emitted triangle winding, unit normals, index
bounds, exact node transforms, alternating links, hull half-spaces and spike
positions. It confirms GLB vertex/normal/UV bytes match the NIF writer input.
The NIF writer saves and reloads the output with nifly and checks the compound
collision and hierarchy. DDS validation decodes every mip of every generated map
(231 mip images for the current 21 DDS files).

These are development assets. A NIF parser round-trip cannot prove that Skyrim
VR instantiates the Havok body correctly, that its collision follows the
runtime solver, or that the weapon deals native melee damage.

The front reference does not specify the back and underside. The current
emblem uses the full diamond in the supplied texture, with shallow image-derived
relief. It is not a recovered sculpture or an exact surface scan.
Collar ornament, spike profile and etched surface details are still less rich
than the supplied reference. The previews use a software material illustration;
the actual game's lighting, mip bias and environment shader remain unverified.
The GLB uses simplified PBR materials and is intended for geometry inspection.


## Current curved emblem and supplied materials — 0.5.3

`Source/Textures/source_manifest.json` identifies all eight images from the
user's `テクスチャ.zip`, including the archive hash, original image hashes and
normalized source hashes. The repository stores 1024-square JPEG derivatives
with recorded resize/encoding settings; the original PNGs remain in the user
attachment. `generate_textures.py` applies deterministic technical crops and
material processing. The generated `material_generation.json` records those
choices and source identities. No generative repaint is part of this pipeline.

| Source image | Weapon part | DDS base |
| --- | --- | --- |
| 鉄球.png | Black iron ball | `cms_metal` |
| スパイク.png | Spikes and their worn tips | `cms_spike` |
| チェーン.png | Chain links and connecting hardware | `cms_chain` |
| リング状エンブレム.png | Decorative handle collars | `cms_ring` |
| 木.png | Exposed wooden shaft | `cms_wood` |
| 革.png | Leather grip | `cms_leather` |
| 革のベルト.png | Crossed leather cords | `cms_cord` |
| エンブレム.png | Curved diamond plaque face | `cms_emblem` |

Every base has `_d.dds` and `_n.dds`. Metal, spike, chain, ring and emblem also
have `_m.dds`. The emblem is mapped once; it is never tiled across the ball.
The provided color images include baked lighting. Derived height, normal,
specular and environment response are authored approximations, not measured
PBR maps; the image colors cannot independently establish physical surface depth.

`emblem_relief.py` makes a dense closed plaque following the head sphere. The
new image includes both the dragon and diamond border, so the previous separate
dragon extrusion and frame are removed. Image coordinates are preserved across
the face. A low-frequency luminance-derived displacement gives the metal shallow
relief; its small scratches remain texture detail. The back closes inside the
ball. The emitted `asset_manifest.json` records the exact radii, displacement
limit, source mapping, mesh counts and face ranges used by the validator.

The independent geometry checks inspect actual emitted vertices and UVs, curved
front/back separation, closed side walls, image mapping and triangle winding.
The existing node and collision contracts remain unchanged. Decoration is not
added to the damage compound. Front and oblique emblem previews come from this
actual mesh, using the same material images as the NIF/GLB generation.

### Matched Windows package

The NIF workflow runs `Tools/write_asset_provenance.py` after generation.
`ASSET_BUILD_PROVENANCE.json` binds the source commit and checked-out asset inputs
to the generated NIF, DDS and material/geometry validation manifests by SHA-256.
`Tools/package_visual_test.py` checks that provenance against the local source
and requires the DLL's own commit, version, source manifest and binary hash.
Git LF/CRLF differences are normalized only for text; image inputs remain exact.

Packaging reads the custom DDS references from the actual NIF, requires the
emitted DDS set to match, validates dimensions/full mip chains and compares each
DDS with its decode report. The verified vanilla `ShinyDull_e.dds` cubemap remains
an external game dependency. The package includes neither original material
images nor game-owned cubemap data. Runtime collision and equipment-drop gates
remain incomplete.


## Historical sculpt revision — 0.5.1, 2026-10-06

The rejected smooth first model has been revised at the mesh level, not merely
recolored. Before the exact emblem replacement below, this revision had 41,951 vertices
and 75,994 triangles across the same 24 material shapes. Ball surface radii vary from 148.0 to 159.6 mm due to
actual hammer depressions. Spike roots penetrate the core; their sides have
recessed facets and tips end in small closed worn faces. Every vertex of these
surfaces is validated inside the existing core/spike collision union.

The core collision hull remains radius 160 mm but now uses 170 vertices, filling
a gap that the former sparse hull left below some spike roots. The head still
has 15 convex children. The dimensions and runtime node names are unchanged.

The exposed wood radius averages 31.41 mm near the hand and 27.44 mm near the
chain. Knots, longitudinal fissures and unequal grain ridges are actual vertex
positions. The leather thickens toward the pommel and has local depressions
under the crossed laces, raised diamond panels, wrinkles and rolled worn edges.
The grip and wood remain continuous surfaces with normals calculated from the
sculpted geometry. The collar at the hand is wider than the chain collar.

The metal cubemap is `textures\cubemaps\ShinyDull_e.dds`, verified in the
user-supplied uncompressed vanilla `trapmace01.nif`, `ironmace.nif` and
`steelmace.nif` in ReferenceBundle. No cubemap from the game is redistributed.
Metal normal-alpha specular and environment masks are used by the preview,
with lower-gloss black iron and brighter worn relief edges.

Normal and UV contract: authoring UVs use V up; the CPU render samples source
PNGs at image row 1-V. GLB keeps those UVs and flips its embedded diffuse and
normal images vertically, without changing the normal green channel. The NIF
writer flips V before computing tangents. DDS normal maps therefore invert the
source green channel once to preserve the same physical slopes. The material
encoder and geometry validator check these conversions independently.

Review images include full weapon, forged head and tapered handle
closeups, all rendered from the emitted mesh source. The CPU preview remains a
material illustration, not Skyrim footage; exact game shading and Havok
instantiation still need Windows build and in-game verification. Decoration
and the unseen rear still involve interpretation of the single reference.

That revision used a 0.34 x 0.38 UV window per spike so the iron's
hammer marks stay broad at that physical scale. Lacing then used the existing wood
color map tinted as light brown hide, the leather normal map, and the nonmetal
leather shader. Version 0.5.3 replaces both assignments with dedicated supplied
spike and cord materials. CPU renders use bilinear
sampling and mip levels selected from UV derivatives to prevent wood-grain
moire. These sampling changes also appear in the exported material definitions.


### Pole determinism regression

Windows/Linux CI comparison exposed a real singularity in the forged ball:
longitude-dependent radius displacement had made each nominal pole into a
column of different points. The resulting thin cap faces could reverse winding
under platform rounding, and the per-wedge pole normals differed substantially.
The corrected generator uses exact (0,0,+/-1) pole directions, smoothly damps
the longitude displacement to zero at each pole, and assigns a shared normal
to all UV copies of a collapsed pole. The 160 degenerate cap triangles are now
absent. The independent emitted-asset validator requires exact pole position
and normal equality and outward normals. It rejects the earlier Windows
artifact and accepts the corrected local build. Windows parity is rechecked
through the next CI build; the local check alone is not a Windows result.


## Historical contour revision — 0.5.2, 2026-10-06

Version 0.5.2 removed the invented dragon. `skyrim_emblem_contours.json` and its
review SVG trace the user's `26f5726c33767d5215c05bbbac1fd8cf.jpg` (480 x 800,
SHA-256 `a5112dac7cc8ff41ca7cc300d6bbf82611d95a4d605fe66c5e2b92850c3b27b6`).
`trace_emblem_reference.py` records extraction, simplification and triangulation.
That build consumed the frozen JSON, without needing the original JPEG. These
files remain as historical provenance; the current build uses the newly supplied
full-diamond texture instead of that separate contour.

The connected outline has 1,398 vertices and 1,396 constrained front triangles.
The trace preserves the source asymmetry, open upper wings, curved neck, lower
limb gaps and crooked tail. Its large negative spaces are open bays, not sealed
holes. Against the extracted source mask, the trace has 99.2549% intersection
over union and a 1.414-pixel maximum boundary distance. Small dark metal pits
inside the symbol are surface shading rather than through-holes.

The previous `emblem_relief.py` uniformly scaled this outline to 152.51 mm high and
extrudes it as opaque metal geometry with closed sides and back. The fit uses
the inner diamond's half-width and half-height, leaving an 8% margin; it does
not squeeze the mark horizontally or fill its bays. The authored depth is
11.6 mm. This is a straight extrusion, not a recovered 3D scan or a bevelled
reconstruction of every facet in the photograph. The clean face samples a
small existing iron texture patch; there is no decal, alpha-cutout replacement,
or additional material slot.

That complete model had 49,415 vertices and 80,528 triangles, in
24 material shapes and the same 17 nodes. The 15 collision hulls and runtime
contracts are unchanged. Its Skyrim-unit AABB is
`(-15.382532, -20.052493, -11.095414)` to
`(15.382610, 117.866746, 11.926509)`, within the existing ESP bounds.

The 0.5.2 validator independently reversed the emitted crest
rotation and compared every contour point and front triangle with the trace.
It checks projected area, inner-diamond clearance and each full-depth side
wall. The local NIF writer reloads the actual exported file and verifies its
hierarchy, meshes and compound collision. These passed locally; the matching
Windows build and actual Skyrim appearance are separate checks.

The CPU renderer additionally writes `ChainMorningstar_emblem_front.png`
(upright orthographic front) and `ChainMorningstar_emblem_relief.png` (oblique
view of actual depth). Those views isolate the real relief vertices from the
same model that is exported to NIF/GLB. Full weapon and head views include the
new mounted emblem. The renderer applies tangent-space normals even to the
small UV triangles of the traced contour, avoiding triangle-dependent shading.
