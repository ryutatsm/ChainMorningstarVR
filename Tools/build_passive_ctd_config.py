"""Build a local Vortex configuration overlay. Never writes the input INI or game files."""
from pathlib import Path
import argparse, configparser, difflib, hashlib, json, re, zipfile

def build(input_ini: Path, capture_dir: Path, output: Path):
    original=input_ini.read_bytes()
    before=original.decode('utf-8-sig')
    parser=configparser.ConfigParser(interpolation=None)
    parser.read_string(before)
    assert parser['Debug'].getboolean('Auto Upload Crash Log') is False
    assert not parser['Debug'].get('Pastebin API Key','').strip(), 'Do not package a secret API key'
    assert capture_dir.is_absolute() and '\n' not in str(capture_dir)
    changes={'Crash Log Write Minidump':'true','Crashlog Directory':str(capture_dir),
             'Max Minidumps':'2','Max Crash Logs':'100'}
    after=before
    for key,value in changes.items():
        after,n=re.subn(r'(?m)^'+re.escape(key)+r'\s*=[^\r\n]*',lambda m:key+' = '+value,after)
        assert n==1,(key,n)
    check=configparser.ConfigParser(interpolation=None)
    check.read_string(after)
    actual={(s,k) for s in parser.sections() for k,v in parser[s].items() if check[s][k]!=v}
    expected={('Debug',k.lower()) for k,v in changes.items() if parser['Debug'][k]!=v}
    assert actual==expected
    assert check['Debug'].getboolean('Thread Dump Write Minidump') is False
    assert check['Debug'].getboolean('Wait for Debugger for Crash') is False
    output.mkdir(parents=True,exist_ok=True)
    backup=output/'CrashLogger-original-backup.ini'
    assert not backup.exists() or backup.read_bytes()==original, 'Preserve existing backup; use another output directory'
    package=output/'SkyrimVR-Passive-CTD-Capture-Config.zip'
    data=after.encode('utf-8')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('SKSE/Plugins/CrashLogger.ini',data)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert z.namelist()==['SKSE/Plugins/CrashLogger.ini']
        assert z.read(z.namelist()[0])==data
    assert input_ini.read_bytes()==original
    backup.write_bytes(original)
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original/CrashLogger.ini',tofile='candidate/CrashLogger.ini'))
    (output/'CTD_CAPTURE_CONFIG_DIFF.txt').write_text(diff,encoding='utf-8',newline='')
    evidence={'original_ini_sha256':hashlib.sha256(original).hexdigest(),
              'candidate_ini_sha256':hashlib.sha256(data).hexdigest(),
              'zip_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
              'changed_keys':list(changes),'capture_directory':str(capture_dir),
              'auto_upload':False,'deployed':False,'game_tested':False,
              'retention_note':'v1.25.0 cleans before writing: setting 2 may leave 3 dump files',
              'dump_kind':'Full process memory, handles, threads, unloaded modules'}
    (output/'CTD_CAPTURE_CONFIG_VERIFICATION.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return evidence

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ini',type=Path,required=True)
    ap.add_argument('--capture-dir',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    print(json.dumps(build(args.ini,args.capture_dir,args.out),ensure_ascii=False,indent=2))
