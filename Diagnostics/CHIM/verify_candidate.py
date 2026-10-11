"""Verify the pinned external source and extract the actual changed C++ blocks.

Only uses the separate CHIM checkout and scratch output. Does not deploy or run Skyrim.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

SOURCE_COMMIT = '12e035d0a810b9b932fe2df1f688407a72cd27a1'
PLUGIN_SHA256 = '282958ce7c1666bdc8dcd18ea09ff27e0151be4e43458d574662d2f1d2215f23'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkout',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    repo=args.checkout.resolve()
    def git(*a): return subprocess.check_output(['git',*a],cwd=repo)
    assert git('rev-parse','HEAD').decode().strip()==SOURCE_COMMIT
    original=git('show','HEAD:Plugin/Plugin.cpp').decode('utf-8')
    assert hashlib.sha256(original.encode()).hexdigest()==PLUGIN_SHA256
    patched=(repo/'Plugin/Plugin.cpp').read_text(encoding='utf-8')
    assert 'RE::NiPointer<RE::TESObjectREFR> cameraRef;' in patched
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    for name,text,marker in [('original',original,'                auto cameraObject ='),
                             ('patched',patched,'                // A non-zero ObjectRefHandle')]:
        start=text.index(marker,text.index('} else if (topicActor && !topicEnded)'))
        stop=text.index('                        if (targetActor == topicActor) {',start)
        block=text[start:stop]
        if name=='patched':
            assert 'cameraObject' not in block
            assert block.count('GetActiveTarget().get()')==1
            assert 'cameraRef = player->GetGrabbedRef();' in block
        snippet=block+'                        if (targetActor == topicActor) { observed(*targetActor); }\n                    }\n                }\n'
        (out/(name+'.inc')).write_text(snippet,encoding='utf-8')
    shutil.copy2(Path(__file__).with_name('regression.cpp'),out/'regression.cpp')
    evidence=dict(upstream_repository='https://github.com/Dwemer-Dynamics/CHIM',
        source_commit=SOURCE_COMMIT,original_plugin_sha256=PLUGIN_SHA256,
        patched_plugin_sha256=hashlib.sha256(patched.encode()).hexdigest(),
        installed_dll_sha256='2d4b7cd20c2612f44b4a1153b306b39b47bacc12d9e1dc3ffea961dabd84b96f',
        installed_binary_build_provenance_confirmed=False,
        regression_method='Actual original/patched source blocks, mocked engine API and smart-pointer ownership',
        game_tested=False,deployed=False)
    (out/'SOURCE_EVIDENCE.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print('Pinned source and extracted regression blocks verified.')

if __name__=='__main__': main()
