"""Package the spark DLL with the SHA-pinned user-approved assets, without visual regeneration."""
import argparse
import json
import re
import struct
from pathlib import Path
from package_world_impact_test import (
    ROOT, BASE, BASE_SHA, DLL, ESP, WAV, append_impact, synthesize,
    read_zip, verify_sums, game_files, write_zip, sha, require, source_proof,
)

VERSION = "1.0.1-sparks"
MODEL = "Effects\\ImpactEffects\\FXMetalSparkImpactBlunt.nif"


def compose(stage, commit):
    require(re.fullmatch("[0-9a-f]{40}", commit), "Full source commit required")
    raw = BASE.read_bytes()
    require(sha(raw) == BASE_SHA, "Visual baseline changed")
    baseline = read_zip(raw)
    verify_sums(baseline, "SHA256SUMS.txt")
    files = dict(game_files(baseline))
    files[ESP] = append_impact(files[ESP])
    files[WAV], audio = synthesize()
    approved = json.loads((ROOT / "Assets/EquipmentSparkBaseline/accepted_game_files.json").read_text(encoding="utf-8"))
    require(set(game_files(files)) == set(approved) and len(approved) == 28, "Wrong game file set")
    for name, digest in approved.items():
        if name != DLL:
            require(sha(files[name]) == digest, "Approved asset changed: " + name)

    dll = (stage / DLL).read_bytes()
    require(dll[:2] == b"MZ", "Missing DOS header")
    pe = struct.unpack_from("<I", dll, 60)[0]
    require(dll[pe:pe+4] == b"PE\0\0" and struct.unpack_from("<H", dll, pe+4)[0] == 0x8664
            and struct.unpack_from("<H", dll, pe+24)[0] == 0x20B, "Not an x64 DLL")
    require(VERSION.encode() in dll and MODEL.encode() in dll and b"CMS equipment-drop sparks:" in dll,
            "Wrong spark build")
    require((stage / "ChainMorningstarVR.dll.sha256").read_text(encoding="utf-8-sig").strip() == sha(dll),
            "DLL stage checksum mismatch")
    status = (stage / "BUILD_STATUS.txt").read_text(encoding="utf-8-sig")
    require("Commit: " + commit in status and VERSION in status, "DLL source/build mismatch")
    files[DLL] = dll
    for name in ("LICENSES/HIGGS_GPL-3.0.txt", "THIRD_PARTY_NOTICES.txt"):
        files[name] = baseline[name]
    files["THIRD_PARTY_NOTICES.txt"] += ("\nDelivered runtime source: https://github.com/ryutatsm/ChainMorningstarVR/tree/" + commit + "\n").encode()
    files.update(source_proof(stage))
    files["Provenance/DLL_BUILD_STATUS.txt"] = (stage / "BUILD_STATUS.txt").read_bytes()
    files["Provenance/PRIOR_VISUAL_BUILD.json"] = baseline["BUILD_PROVENANCE.json"]
    files["README_JA.txt"] = (ROOT / "Docs/EQUIPMENT_SPARKS_INSTALL_JA.txt").read_bytes()
    report = dict(
        format="cms-equipment-sparks-unified-v1", version=VERSION + "-unified",
        source_commit=commit, runtime_dll_build_label=VERSION,
        baseline_visual_zip_sha256=BASE_SHA,
        accepted_game_payload_source="57e61bee55fcb6fad566687e13db804393662bfe",
        changed_game_files=[DLL], preserved_game_file_count=27,
        game_files={n: sha(v) for n, v in sorted(game_files(files).items())},
        spark_effect=dict(model=MODEL, vanilla_record="Skyrim.esm:0004BB53",
                          lifetime_seconds=0.35, scale=1.0, target_attached=False,
                          trigger="RemoveItem returned a dropped reference after the existing equipment lottery",
                          engine_api="BSTempEffectParticle::Spawn; NiPoint3 rotation overload",
                          vr_address_library_id=29218, vr_1_4_15_offset="0x45B4F0"),
        total_triangles=3996, visible_triangles=2900, blood_triangles=1096,
        chain_links=19, runtime_nodes=22, collision_hulls=15, dds_count=21,
        impact_audio=audio, equipment_drop_audio_unchanged=True,
        equipment_drop_probability_unchanged=True,
        new_runtime_vr_test_passed=False, spark_visibility_in_vr_confirmed=False,
        xedit_check_for_errors_passed=False, ctd_resolved=False, formal_release=False,
    )
    files["BUILD_PROVENANCE.json"] = (json.dumps(report, indent=2) + "\n").encode()
    files["SHA256SUMS.txt"] = "".join(sha(v) + "  " + n + "\n" for n, v in sorted(files.items())).encode()
    verify_sums(files, "SHA256SUMS.txt")
    return files, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll-stage", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files, report = compose(args.dll_stage, args.source_commit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_zip(args.out, files)
    report["zip_sha256"] = sha(args.out.read_bytes())
    args.out.with_suffix(".provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EQUIPMENT_SPARKS_UNIFIED_PASS", report["zip_sha256"], "27 accepted assets unchanged; only DLL replaced")
