"""One Vortex-installable test MOD: pinned audit6 runtime plus approved visuals.

This never rebuilds the runtime or invokes original model generators. The five
visual replacements must match reviewed hashes; all other game bytes come from
the immutable diagnostic archive. Original provenance is explicitly historical.
"""
import argparse,hashlib,io,json,re,struct,subprocess,sys
from pathlib import Path,PurePosixPath
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA='63c6a4afaa5d032f58b66e4ce13c41f3ef410df8d19c15ee5714614d835bcd70'
DLL='SKSE/Plugins/ChainMorningstarVR.dll'
ESP='ChainMorningstarVR.esp'
NIF='meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif'
REPLACEMENTS={NIF}|{'textures/weapons/ChainMorningstarVR/'+n for n in (
    'cms_emblem_n.dds','cms_leather_d.dds','cms_leather_n.dds','cms_wood_n.dds')}
OVERLAY_META={'OPTIMIZED_VISUAL_PROVENANCE.json','README_OPTIMIZED_TEST_JA.txt','SHA256SUMS_OPTIMIZED_TEST.txt'}

def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def read_zip(data):
    with ZipFile(io.BytesIO(data)) as z:
        names=z.namelist();seen=set()
        for name in names:
            p=PurePosixPath(name)
            require(not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name
                    and p.as_posix()==name and not name.endswith('/'),'Unsafe ZIP path: '+name)
            require(name.lower() not in seen,'Duplicate/case-colliding ZIP entry: '+name)
            seen.add(name.lower())
        require(z.testzip() is None,'ZIP CRC failed')
        return {n:z.read(n) for n in names}

def verify_sums(files,name):
    records={}
    for line in files[name].decode('utf-8-sig').splitlines():
        digest,path=line.split('  ',1)
        require(re.fullmatch('[0-9a-f]{64}',digest) and path in files and path not in records,'Invalid SHA256 entry')
        require(sha(files[path])==digest,'Internal SHA256 mismatch: '+path);records[path]=digest
    require(set(records)==set(files)-{name},'Incomplete SHA256 list')

def game_files(files):
    return {n:v for n,v in files.items() if n==ESP or n.startswith(('SKSE/','meshes/','textures/','sound/'))}

def runtime_checks(files):
    sys.path.insert(0,str(ROOT/'Tests'))
    from test_plugin_binary import inspect_binary
    records,groups=inspect_binary(files[ESP])
    require(groups==[b'STAT',b'WEAP',b'SNDR'],'Wrong ESP group set')
    weap=records[(b'WEAP',0x01000800)];stat=records[(b'STAT',0x01000801)]
    require(weap[b'MODL']==stat[b'MODL']==b'weapons\\ChainMorningstarVR\\ChainMorningstar.nif\0','ESP model path changed')
    require(struct.unpack('<IfH',weap[b'DATA'])==(550,17.,44),'Weapon stats changed')
    require(weap[b'WNAM']==struct.pack('<I',0x01000801),'First-person STAT changed')
    dll=files[DLL];require(dll[:2]==b'MZ','DLL DOS header missing')
    pe=struct.unpack_from('<I',dll,60)[0]
    require(dll[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',dll,pe+4)[0]==0x8664
            and struct.unpack_from('<H',dll,pe+24)[0]==0x20b,'DLL must remain x64')
    require(b'1.0.0-audit6' in dll,'Wrong runtime build label')
    for i,name in enumerate(('iron_scrape.wav','air_cut.wav','disarm_strike.wav')):
        sound=records[(b'SNDR',0x01000802+i)]
        require(sound[b'ANAM']==('fx\\ChainMorningstarVR\\'+name+'\0').encode(),'Audio descriptor changed')
        require(sound[b'LNAM'][1]&0x38==(8 if i==0 else 0),'Audio loop flags changed')
        raw=files['sound/fx/ChainMorningstarVR/'+name]
        require(raw[:4]==b'RIFF' and raw[8:12]==b'WAVE','Invalid WAV')
    sys.path.insert(0,str(ROOT/'Tools'))
    from package_visual_test import texture_references,VANILLA_TEXTURES
    custom,vanilla=texture_references(files[NIF]);lower={n.lower() for n in files}
    require({n.lower() for n in custom}<=lower,'Missing NIF texture resource')
    require({n.lower() for n in vanilla}==VANILLA_TEXTURES,'Vanilla texture dependency changed')
    for name in ('CMS_ROOT','CMS_ChainAnchor','CMS_HeadNode','BloodFX','BloodLighting'):
        require(name.encode() in files[NIF],'Required NIF node missing: '+name)
    for i in range(19):require(f'CMS_LinkNode_{i:02d}'.encode() in files[NIF],'Missing chain link')
    for name,data in files.items():
        if not name.endswith('.dds'):continue
        require(data[:4]==b'DDS ' and data[84:88]==b'DXT5','Wrong DDS header')
        require(struct.unpack_from('<II',data,12)==(1024,1024) and struct.unpack_from('<I',data,28)[0]==11,'DDS size/mips changed')
        require(len(data)==128+sum(max(1,(max(1,1024>>i)+3)//4)**2*16 for i in range(11)),'DDS length/mips mismatch')
    return dict(esp_structure_checked=True,dll_x64_checked=True,audio_descriptors_checked=True,
                nif_texture_references_complete=True,dds_count=21,chain_links=19)

def compose(base_data,overlay_data,approved,packaging_commit):
    require(sha(base_data)==BASE_SHA,'Wrong audit6 baseline ZIP')
    require(approved['format']=='cms-audit6-unified-payload-v1' and approved['baseline_zip_sha256']==BASE_SHA,'Wrong approved input manifest')
    require(set(approved['game_files'])==REPLACEMENTS,'Approved replacement set changed')
    require(re.fullmatch('[0-9a-f]{40}',packaging_commit),'Full packaging commit required')
    # Saved inputs and packaging code now share one committed snapshot. Resolve
    # this explicit marker to its actual Git SHA; avoid a circular self-hash.
    visual_commit=approved['visual_input_commit']
    if visual_commit=='packaging-commit':visual_commit=packaging_commit
    require(re.fullmatch('[0-9a-f]{40}',visual_commit),'Full visual input commit required')
    base=read_zip(base_data);visual=read_zip(overlay_data)
    verify_sums(base,'SHA256SUMS.txt');verify_sums(visual,'SHA256SUMS_OPTIMIZED_TEST.txt')
    require(set(visual)==REPLACEMENTS|OVERLAY_META,'Overlay must contain only five visual assets and metadata')
    for name in REPLACEMENTS:require(sha(visual[name])==approved['game_files'][name],'Unapproved visual asset: '+name)
    edit=json.loads(visual['OPTIMIZED_VISUAL_PROVENANCE.json'])
    require(edit['baseline_zip_sha256']==BASE_SHA and edit['format']=='cms-blender-under4k-v2','Wrong visual baseline/route')
    require(edit['source_loaded_from_saved_file'] and edit['nodes_and_collision_bytes_preserved'],'Missing authored visual contract')
    require(edit['nif_writer_baseline_reproduction_verified'] and edit['blood_regenerated_by_pinned_writer'],'Missing NIF writer/blood proof')
    require(edit['nif_total_triangles']==approved['nif_total_triangles']==3996 and
            edit['after_triangles']==2900 and edit['blood_triangles']==1096,'Wrong inclusive triangle count')
    require(edit['nif_sha256']==sha(visual[NIF]) and edit['chain_links']==19 and edit['node_count']==22 and edit['collision_hulls']==15,'Wrong visual identity')
    base_game=game_files(base)
    require(len(base_game)==27 and REPLACEMENTS<=set(base_game),'Incomplete audit6 game payload')
    require(sum(n.endswith('.dds') for n in base_game)==21 and sum(n.endswith('.wav') for n in base_game)==3,'Incomplete textures/audio')
    files=dict(base_game);files.update({n:visual[n] for n in REPLACEMENTS})
    for name in set(base_game)-REPLACEMENTS:require(files[name]==base_game[name],'Runtime bytes changed: '+name)
    checks=runtime_checks(files)
    files['LICENSES/HIGGS_GPL-3.0.txt']=base['LICENSES/HIGGS_GPL-3.0.txt']
    files['THIRD_PARTY_NOTICES.txt']=base['THIRD_PARTY_NOTICES.txt']
    files['Provenance/AUDIT6_ORIGINAL_BUILD.json']=base['BUILD_PROVENANCE.json']
    files['Provenance/VISUAL_EDIT_SOURCE.json']=visual['OPTIMIZED_VISUAL_PROVENANCE.json']
    files['README_JA.txt']=(
        'チェーンドモーニングスター audit6 統合・外観テスト版（3,996三角形）\n\n'
        'audit6本体のDLL・ESP・音声・全テクスチャと、最新の軽量化モデル・革の縁修正を1つに統合しました。\n'
        'このChainMorningstarVR統合版だけを有効にします。別途audit6本体や外観テストを有効にする必要はありません。\n'
        '既存のSKSEVR・HIGGSなどの前提MODは引き続き有効にしてください。\n\n'
        '導入:\n'
        '1. Skyrim VRを終了します。\n'
        '2. Vortexで旧ChainMorningstarVR-1.0.0-audit6-diagnosticと、以前の外観テストをすべて無効化します。\n'
        '3. 今回の統合ZIPを「ファイルからインストール」で追加し、有効にします。ZIPを展開する必要はありません。\n'
        '4. ChainMorningstarVR.espを有効にし、「MODを配置」を実行します。\n'
        '5. いつものSKSEVR起動方法でゲームを開始してください。ESPは元audit6とバイト同一、武器の登録IDも同じです。\n\n'
        '今回の内容:\n'
        '表示用2,900、血用1,096、NIF総計3,996三角形。31表示メッシュ、22ノード、19鎖節、15衝突形状を維持。\n'
        '革の上下を木へつながる薄い縁で閉じています。紐とエンブレムは色・ノーマルマップによる凹凸表現です。\n'
        'DLL・ESP・音声はaudit6と同じです。内部バージョン表示やログのcms_versionは1.0.0-audit6のままです。\n'
        '統合によって物理演算を変更したり、追加でFPSが改善するものではありません。元の上書き構成と同じゲーム用ファイルです。\n\n'
        '戻し方:\n'
        '今回の統合版を無効化し、元audit6本体を再び有効にして「MODを配置」を実行します。\n'
        '以前の外観へ戻す場合は、その外観テスト1つも有効にし、本体より後に配置します。\n'
        '旧MODと元ZIPは動作確認までバックアップとして残せます。統合版が正常なら旧MODを削除して構いません。\n\n'
        '検証範囲:\n'
        '元archive・5置換ファイル・全ゲーム用ファイルのSHA256、ZIP CRC、ESP構造、x64 DLL、音声参照、NIF/DDS参照を確認。\n'
        'Provenance内の2JSONは元入力の歴史的記録です。現在の統合ファイル一覧はBUILD_PROVENANCE.jsonとSHA256SUMS.txtを参照。\n'
        'Skyrim VR実機、FPS、xEdit Check for Errors、実際の掴み/血/摩擦/装備解除/音はこの統合版では未確認です。\n'
        '正式完成版ではなく、ユーザー指定による統合テスト版です。\n'
    ).encode('utf-8-sig')
    report=dict(format='cms-audit6-unified-test-v1',version='1.0.0-audit6-unified-3996-test',
        release_channel='unified-visual-test',completed_release=False,requires_separate_audit6_mod=False,
        standalone_chainmorningstar_package=True,external_prerequisites_unchanged=True,
        baseline_zip_sha256=BASE_SHA,overlay_zip_sha256=sha(overlay_data),
        runtime_source_commit='df3ef906a7927516263b567817900cc125d5f860',
        visual_input_commit=visual_commit,packaging_commit=packaging_commit,
        runtime_dll_build_label='1.0.0-audit6',draw_triangles=2900,blood_triangles=1096,nif_total_triangles=3996,
        baseline_game_files=27,replaced_game_files=sorted(REPLACEMENTS),
        dll_esp_audio_byte_identical_to_audit6=True,all_other_game_files_byte_identical_to_audit6=True,
        all_game_files_equal_to_prior_base_plus_overlay=True,
        structural_checks=checks,runtime_tested=False,xedit_tested=False,fps_measured=False,
        packaging_tool_sha256=sha(Path(__file__).read_bytes()),
        files={n:dict(bytes=len(v),sha256=sha(v),source='visual-edit' if n in REPLACEMENTS else 'audit6' if n in base_game else 'metadata') for n,v in sorted(files.items())})
    files['BUILD_PROVENANCE.json']=(json.dumps(report,indent=2)+'\n').encode()
    files['SHA256SUMS.txt']=''.join(sha(v)+'  '+n+'\n' for n,v in sorted(files.items())).encode()
    return files,report

def write_zip(out,files):
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=ZipInfo(name,date_time=(2026,10,11,0,0,0));info.compress_type=ZIP_DEFLATED
            info.create_system=3;info.external_attr=0o100644<<16
            z.writestr(info,data,compresslevel=9)
    actual=read_zip(out.read_bytes());require(actual==files,'Unified ZIP reread mismatch')
    verify_sums(actual,'SHA256SUMS.txt')

def main(a):
    commit=a.packaging_commit or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files,report=compose(a.baseline_zip.read_bytes(),a.overlay.read_bytes(),json.loads(a.inputs.read_text()),commit)
    a.out.parent.mkdir(parents=True,exist_ok=True);write_zip(a.out,files)
    report.update(zip_sha256=sha(a.out.read_bytes()),zip_bytes=a.out.stat().st_size,zip_crc_and_internal_hashes_verified=True)
    a.out.with_suffix('.provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('UNIFIED_TEST_PACKAGE_PASS',a.out,'27 game files; only five visuals replaced; 3996 triangles',report['zip_sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('baseline-zip','overlay','inputs','out'):p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--packaging-commit');main(p.parse_args())
