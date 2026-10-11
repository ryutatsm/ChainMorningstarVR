"""Unified audit8 sound5 quieter world-impact test. Preserve the user-approved visual payload.

This route never invokes a mesh/texture generator. Runtime sources remain at
audit8; the authored impact WAV is replaced with the selected quieter sample.
"""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Tools/Blender'))
from package_unified_test import read_zip,verify_sums,game_files,write_zip,sha,require,DLL,ESP,NIF
sys.path.insert(0,str(ROOT/'Source/xEdit'))
from add_world_impact import append_impact
sys.path.insert(0,str(ROOT/'Source/Audio'))
from generate_world_impact import synthesize
sys.path.insert(0,str(ROOT/'Tests'))
from test_plugin_binary import inspect_binary
BASE_SHA='0915963d897a17e2217da1b755e081efc23a1ba6815bc3a086eb7c748dac1224'
BASE=ROOT/'Assets/WorldImpactBaseline/ChainMorningstarVR-1.0.0-audit6-unified-spike-contact-test.zip'
WAV='sound/fx/ChainMorningstarVR/iron_impact.wav'

def verify_dll(dll):
    require(dll[:2]==b'MZ','Missing DLL DOS header')
    pe=struct.unpack_from('<I',dll,60)[0]
    require(dll[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',dll,pe+4)[0]==0x8664
            and struct.unpack_from('<H',dll,pe+24)[0]==0x20b,'DLL must be x64 PE32+')
    require(b'1.0.0-audit8' in dll and b'follow=head soundID=' in dll,'Wrong runtime/audio build')

def source_proof(stage):
    proofs={}
    for name,base in (('DLL_SOURCE_SHA256.json',ROOT/'Source/SKSE'),
                      ('DLL_THIRD_PARTY_SHA256.json',ROOT)):
        raw=(stage/name).read_bytes(); entries=json.loads(raw.decode('utf-8-sig'))
        for e in entries:
            p=base/e['path']; require(p.is_file() and p.resolve().is_relative_to(base.resolve()),'Invalid source proof path')
            require(sha(p.read_bytes())==e['sha256'],'Built source mismatch: '+e['path'])
        expected={p.relative_to(base).as_posix() for p in
                  ((ROOT/'Source/SKSE').rglob('*') if 'SOURCE' in name else (ROOT/'Source/ThirdParty').rglob('*'))
                  if p.is_file() and 'build' not in p.relative_to(base).parts}
        require({e['path'] for e in entries}==expected,'Incomplete built-source proof')
        proofs['Provenance/'+name]=raw
    return proofs

def compose(stage,commit):
    require(re.fullmatch('[0-9a-f]{40}',commit),'Full source commit required')
    baseline=BASE.read_bytes(); require(sha(baseline)==BASE_SHA,'Unapproved visual/runtime baseline')
    old=read_zip(baseline);verify_sums(old,'SHA256SUMS.txt'); original=game_files(old)
    require(len(original)==27 and sha(original[NIF])=='8d07faf527074902495386f0e9c8a2b8e53ffd8b0e9d33f27c401f8656a2302f','Wrong successful visual payload')
    dll=(stage/DLL).read_bytes();verify_dll(dll)
    require((stage/'ChainMorningstarVR.dll.sha256').read_text(encoding='utf-8-sig').strip()==sha(dll),'DLL stage checksum mismatch')
    status=(stage/'BUILD_STATUS.txt').read_text(encoding='utf-8-sig')
    require('Commit: '+commit in status and '1.0.0-audit8' in status,'DLL source commit/build mismatch')
    files=dict(original);files[DLL]=dll;files[ESP]=append_impact(original[ESP])
    files[WAV],audio=synthesize()
    records,groups=inspect_binary(files[ESP]);old_records,_=inspect_binary(original[ESP])
    require(groups==[b'STAT',b'WEAP',b'SNDR'],'ESP groups changed')
    require(set(records)==set(old_records)|{(b'SNDR',0x01000805)},'Unexpected ESP record changes')
    for key,fields in old_records.items():
        if key==(b'TES4',0):
            require({k:v for k,v in records[key].items() if k!=b'HEDR'}=={k:v for k,v in fields.items() if k!=b'HEDR'},'ESP header changed')
            require(struct.unpack('<fII',records[key][b'HEDR'])[1:]==(9,0x806),'Wrong ESP count/next ID')
        else:require(records[key]==fields,'Old weapon/audio record changed')
    descriptor=records[(b'SNDR',0x01000805)]
    require(descriptor[b'ANAM']==b'fx\\ChainMorningstarVR\\iron_impact.wav\0' and descriptor[b'LNAM'][1]&0x38==0,'Wrong new audio path/loop flags')
    unchanged=set(original)-{DLL,ESP}
    require(all(files[n]==original[n] for n in unchanged),'Successful game assets changed')
    require(len(game_files(files))==28,'Incomplete unified payload')
    for n in ('LICENSES/HIGGS_GPL-3.0.txt','THIRD_PARTY_NOTICES.txt'):files[n]=old[n]
    files['Provenance/PRIOR_SUCCESSFUL_VISUAL_BUILD.json']=old['BUILD_PROVENANCE.json']
    files.update(source_proof(stage))
    files['Provenance/DLL_BUILD_STATUS.txt']=(stage/'BUILD_STATUS.txt').read_bytes()
    files['README_JA.txt']=(ROOT/'Docs/WORLD_IMPACT_TEST_JA.txt').read_bytes()
    report=dict(format='cms-audit8-world-impact-sound5-test-v3',version='1.0.0-audit8-sound5-quieter-unified-test',
                source_commit=commit,baseline_zip_sha256=BASE_SHA,
                baseline_visual_source_commit='b46f8d78492090edb66d47d7e345b303cb9b0e0e',
                change_scope=['DLL: rebuilt from byte-identical audit8 SKSE runtime sources; no behavior changes',
                              'ESP: byte-identical to audible audit8 build','WAV: user-selected sample 05, linear gain 0.85 relative to audition sample'],
                preserved_game_files={n:sha(files[n]) for n in sorted(unchanged)},
                game_files={n:sha(v) for n,v in sorted(game_files(files).items())},
                total_triangles=3996,chain_links=19,runtime_nodes=22,collision_hulls=15,
                impact_audio=audio,esp_old_records_preserved=True,dll_x64=True,
                runtime_sources_unchanged_from='b982a3ae5c451353eec31474ad0d21905a6a254a',
                previous_audit8_impact_audible_user_report=True,
                runtime_dll_build_label='1.0.0-audit8',
                vr_audibility_confirmed=False,new_runtime_vr_test_passed=False,
                xedit_check_for_errors_passed=False,formal_release=False)
    files['BUILD_PROVENANCE.json']=(json.dumps(report,indent=2)+'\n').encode()
    files['SHA256SUMS.txt']=''.join(sha(v)+'  '+n+'\n' for n,v in sorted(files.items())).encode()
    return files,report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dll-stage',type=Path,required=True)
    p.add_argument('--source-commit',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    files,report=compose(a.dll_stage,a.source_commit);a.out.parent.mkdir(parents=True,exist_ok=True);write_zip(a.out,files)
    report['zip_sha256']=sha(a.out.read_bytes());a.out.with_suffix('.provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('WORLD_IMPACT_UNIFIED_PACKAGE_PASS',report['zip_sha256'],'28 game files; 25 existing assets unchanged; 3996 triangles')
