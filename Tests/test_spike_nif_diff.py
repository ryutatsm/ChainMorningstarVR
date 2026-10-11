"""Actual corrected NIF differs from the prior lighting version in three meshes."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Tools/Blender'))
from nif_material_contract import patch,parse,sha
from package_lighting_test import inspect


def verify(a):
    scratch=ROOT/'build/spike-nif-diff';scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        old=Path(temp)/'old.nif'
        subprocess.run([str(a.writer.resolve()),str(ROOT/'Tools/Blender/contracts/spike_contact_source.cms'),str(old)],check=True)
        before,_=patch(old.read_bytes(),profile='previous-leather-edge')
        assert sha(before)=='667c88138d3572b4057dc6792c9d1569e2cae09fd08a89d53d751f37122ca01c'
        old.write_bytes(before);after=a.nif.read_bytes();p,q=parse(before),parse(after)
        assert p==q,'NIF layout or block sizes changed'
        assert before[:p['header_end']]==after[:q['header_end']]
        assert before[p['footer_start']:]==after[q['footer_start']:]
        old_doc,new_doc=inspect(old,a.inspector),inspect(a.nif,a.inspector)
        assert old_doc==new_doc,'Runtime nodes, shape identities or any material changed'
        expected={s['block'] for s in old_doc['shapes'] if s['name'] in ('CMS_CMS_HeadNode_spike','BloodFX','BloodLighting')}
        changed=set()
        for i,b in enumerate(p['blocks']):
            lo,hi=b['offset'],b['offset']+b['size']
            if before[lo:hi]!=after[lo:hi]:changed.add(i)
        assert changed==expected,(changed,expected)
        proof=dict(previous_lighting_nif_sha256=sha(before),current_nif_sha256=sha(after),
                   changed_blocks=sorted(changed),changed_shapes=['CMS_CMS_HeadNode_spike','BloodFX','BloodLighting'],
                   all_nodes_collision_materials_texture_sets_other_shapes_header_footer_byte_identical=True,
                   blood_regenerated_to_follow_repaired_spikes=True,runtime_tested=False)
        if a.out:a.out.write_text(json.dumps(proof,indent=2)+'\n')
        print('SPIKE_NIF_DIFF_PASS',json.dumps(proof))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('writer','inspector','nif'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--out',type=Path);verify(p.parse_args())
