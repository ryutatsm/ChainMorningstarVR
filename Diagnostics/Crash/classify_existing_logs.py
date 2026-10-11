"""Read-only classification of existing Skyrim VR CrashLogger text logs.

Does not launch Skyrim, toggle plugins, edit saves, or attribute a cause to a mod.
Offsets apply only to the executable MD5 recorded below. A shutdown-path match
does not prove the user requested shutdown: startup aborts may also tear down.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

EXE_MD5 = "6cc5baea600d6a688a5fa5aa67a54248"
TEARDOWN_FRAMES = [
    0x14339F, 0x12F8514, 0x2A24B2, 0x5D6B79, 0x1440AE,
    0x2959C2, 0x2955C4, 0x5D67E7, 0x5D6452, 0x69D8E4,
    0x1E65D7, 0x5B794E, 0x5B42CA,
]
MIST_MENU_FRAMES = [0x534D71, 0x8DA726, 0xF1BA95]


def classify(data: bytes, name: str) -> dict:
    text = data.decode("utf-8-sig", errors="replace")
    exception = re.search(r'^Unhandled exception.*?\s(\S+\.\w+)\+([0-9A-Fa-f]+)', text, re.M)
    md5 = re.search(r'Executable MD5:\s*([0-9a-fA-F]{32})', text)
    uptime = re.search(r'Process Uptime:.*?\((\d+)ms\)', text)
    callstack = text.split('CALL STACK', 1)[-1].split('REGISTERS:', 1)[0] if 'CALL STACK' in text else ''
    probable = [line for line in callstack.splitlines() if re.match(r'\s*\[\s*\d+\]\[P\]', line)]
    frames = []
    for line in probable:
        match = re.search(r'SkyrimVR\.exe\+([0-9A-Fa-f]+)', line)
        if match:
            frames.append(int(match[1], 16))
    registers = text.split('REGISTERS:', 1)[-1].split('STACK:', 1)[0] if 'REGISTERS:' in text else ''
    regs = {m[1]: int(m[2], 16) for m in re.finditer(r'^\s*(RAX|RBX|RCX|RDI)\s+0x([0-9a-fA-F]+)', registers, re.M)}
    # Limit this to the module list, not stack annotations or plugin names.
    modules = text.split('MODULES:', 1)[-1].split('SKSE PLUGINS:', 1)[0] if 'MODULES:' in text else None
    module = exception[1] if exception else None
    offset = int(exception[2], 16) if exception else None
    supported = bool(md5 and md5[1].lower() == EXE_MD5)
    category = 'unclassified'
    if supported and module == 'SkyrimVR.exe':
        if frames[:len(TEARDOWN_FRAMES)] == TEARDOWN_FRAMES and offset == 0x14339F and regs.get('RDI') == 0x220:
            category = 'actor_shadow_scene_null_during_teardown'
        elif frames[:3] == MIST_MENU_FRAMES and offset == 0x534D71:
            category = 'mist_menu_vr_scene_render_path'
    elif module == 'AIAgent.dll' and offset == 0x1A6F75:
        category = 'aiagent_dialogue_known_fault_offset'
    elif module == 'dxgi.dll' and offset == 0x11511B:
        category = 'reshade_openvr_known_fault_offset'
    return {
        'file': name, 'sha256': hashlib.sha256(data).hexdigest(),
        'fault_module': module, 'fault_rva': hex(offset) if offset is not None else None,
        'exe_md5_matches': supported, 'uptime_ms': int(uptime[1]) if uptime else None,
        'category': category, 'probable_engine_frames': [hex(x) for x in frames],
        'fault_base_value': hex(regs['RDI']) if offset == 0x14339F and 'RDI' in regs else
                            hex(regs['RAX']) if offset == 0x534D71 and 'RAX' in regs else None,
        'cms_module_listed': None if modules is None else bool(re.search(r'^\s*ChainMorningstarVR\.dll\b', modules, re.M)),
        'manual_exit_proven_by_log': False,
        'root_cause_mod_identified': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.log_dir.glob('crash-*.log'))
    if not paths:
        parser.error('No existing crash-*.log files found')
    if args.output.suffix.lower() != '.json' or any(args.output.resolve() == p.resolve() for p in paths):
        parser.error('Output must be a separate .json file')
    rows = [classify(p.read_bytes(), p.name) for p in paths]
    result = {
        'schema': 'cms-existing-crash-classification-v1',
        'read_only_inputs': True, 'game_launched': False,
        'scope': 'Only supplied retained logs; not a crash-rate estimate or a complete session history',
        'interpretation': 'Teardown identifies the active engine path, not why shutdown began or which mod is responsible',
        'count': len(rows), 'categories': dict(Counter(x['category'] for x in rows)), 'logs': rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'count': len(rows), 'categories': result['categories']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
