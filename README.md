# ChainMorningstarVR

Skyrim VR chain morningstar, under development. Audited against main commit
`0777e257d64fcab908df03ff94e7a9af4ff1a0ee` on 2026-10-06.

**0.8.0 size/chain/impact/blood test: Vortex-installable development build.**
The user reported 0.7.0 working normally. Version 0.8.0 scales the approved
model, node offsets, collision hulls and simulation dimensions to 75%, then
adds five matching links (14 → 19). Every link uses the existing non-damaging
swept capsule contacts. The 12 kg head and dark material finish are retained.
Head impacts play Skyrim's heavy-metal sound separately from chain rattles.
Two initially hidden native blood passes follow the actual ball, spikes and
curved emblem; the game's weapon-blood processing controls their display.
See [the implementation and validation notes](Docs/SIZE_CHAIN_BLOOD_080.md).
The [0.6.1 attachment fix](Docs/ATTACHMENT_FIX_061.md) remains in place.
The HIGGS weapon body follows the simulated iron head using the NIF's actual
15 convex collision hulls. Native head contacts feed back into the chain solver.
Certified enemy head or equipped-weapon contacts enter a single 1/3 drop draw;
weapon meshes without usable CPU geometry are conservatively skipped.
Windows compilation and portable tests do not establish in-game compatibility.
There are no registered chain rigid bodies, self-collisions or closed-loop
wrapping constraints. Both-hands-at-once use is unsupported. See the installation
guide for requirements and test limits. The new 0.8.0 behavior needs in-game testing.

The current appearance revision curves the emblem plaque around the iron ball
and uses the supplied texture images for the corresponding weapon parts.
Preview renders show the generated model; Skyrim VR lighting remains unverified.

- [Audit and implementation status](Docs/AUDIT_20261006_JA.md)
- [Build and target-test status](Docs/INSTALL_VR.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Native physics backend design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Do not install historical packages or enable the removed `native-proxy-test`
experiment based on an older handoff. The source tree is authoritative; unused
embedded source ZIPs were removed.
