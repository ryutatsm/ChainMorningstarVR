# ChainMorningstarVR

Skyrim VR chain morningstar, under development. Audited against main commit
`0777e257d64fcab908df03ff94e7a9af4ff1a0ee` on 2026-10-06.

**0.5.2 visual/audio test is not a completed combat mod or a release.**
The moving head has no verified native collision backend. Enemy helmet/weapon
drops have tested source logic but are not connected to gameplay.

- [Audit and implementation status](Docs/AUDIT_20261006_JA.md)
- [Build and target-test status](Docs/INSTALL_VR.md)
- [Required release gates](Docs/RELEASE_GATE_NEW_BUILD.md)
- [Native physics backend design](Docs/NATIVE_BRIDGE_AUDIT_20261006.md)
- [Equipment-drop integration](Docs/EQUIPMENT_DROP_INTEGRATION.md)

Do not install historical packages or enable the removed `native-proxy-test`
experiment based on an older handoff. The source tree is authoritative; unused
embedded source ZIPs were removed.
