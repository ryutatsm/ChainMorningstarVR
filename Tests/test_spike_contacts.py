"""Independent ray/triangle contact check and rejected out-of-scope changes."""
import argparse, copy, json, subprocess, sys, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Tools/Blender'))
from cms_io import load,sha256
import spike_contact_contract as contact


def radial_surface(point,triangles):
    """Moller-Trumbore origin ray, independent of repair half-space algorithm."""
    direction=point/np.linalg.norm(point)
    a=triangles[:,0];e1=triangles[:,1]-a;e2=triangles[:,2]-a
    h=np.cross(direction,e2);det=np.sum(e1*h,axis=1)
    valid=np.abs(det)>1e-12;inv=np.zeros(len(det));inv[valid]=1/det[valid]
    s=-a;u=inv*np.sum(s*h,axis=1);q=np.cross(s,e1)
    v=inv*(q@direction);r=inv*np.sum(e2*q,axis=1)
    hit=valid&(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(r>0)
    if not hit.any():raise AssertionError('No core intersection')
    return float(r[hit].min())


class ContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cms=load(ROOT/'Assets/BlenderFinish/optimized.cms',False)
        cls.old=contact.source();cls.spike=contact.mesh(cls.cms,contact.SPIKE)
        cls.rows=np.array(cls.spike['vertices']);cls.faces=np.array(cls.spike['faces'])

    def test_full_base_edges_inside_actual_triangle_surface(self):
        core=contact.mesh(self.cms,contact.CORE)
        triangles=np.array(core['vertices'])[np.array(core['faces']),:3]
        maximum=-1e9;tested=0
        for ids in contact.components(self.rows,self.faces):
            bottom=ids[np.isclose(self.rows[ids,7],self.rows[ids,7].min(),atol=1e-8)]
            ring=self.rows[bottom];ring=ring[np.argsort(ring[:,6])]
            for a,b in zip(ring[:-1,:3],ring[1:,:3]):
                for t in np.linspace(0,1,65):
                    point=a*(1-t)+b*t
                    maximum=max(maximum,np.linalg.norm(point)-radial_surface(point,triangles));tested+=1
        self.assertLess(maximum,-.0003498)
        self.assertGreater(tested,5000)

    def test_preserves_tips_normals_uv_faces_and_all_other_meshes(self):
        proof=contact.validate_cms(self.cms)
        self.assertEqual(proof['spike_count'],14)
        self.assertTrue(proof['entire_base_polygon_inside_core'])
        self.assertEqual(sum(len(m['faces']) for m in self.cms['meshes']),2900)
        self.assertEqual(sum(len(m['faces']) for m in self.cms['meshes'] if m['name'] in (contact.CORE,contact.SPIKE,'CMS_CMS_HeadNode_emblem'))*2,1096)
        self.assertEqual(self.cms['nodes'],self.old['nodes'])
        self.assertEqual(''.join(self.cms['lines'][self.cms['collision_start']:]),''.join(self.old['lines'][self.old['collision_start']:]))

    def reject(self,mutate,message):
        unsafe=copy.deepcopy(self.cms);mutate(unsafe)
        with self.assertRaisesRegex(ValueError,message):contact.validate_cms(unsafe)

    def test_rejects_detached_base(self):
        self.reject(lambda c:contact.mesh(c,contact.SPIKE)['vertices'][0].__setitem__(0,self.rows[0,0]+.002),'Spike roots')

    def test_rejects_moved_tip(self):
        i=int(np.flatnonzero(self.rows[:,7]==1)[0])
        self.reject(lambda c:contact.mesh(c,contact.SPIKE)['vertices'][i].__setitem__(0,self.rows[i,0]+.000001),'Spike roots')

    def test_rejects_uv_and_normal_changes(self):
        for column in (3,6):
            with self.subTest(column=column):
                self.reject(lambda c:contact.mesh(c,contact.SPIKE)['vertices'][0].__setitem__(column,self.rows[0,column]+.000001),'Canonical spike' if column==3 else 'Spike roots')

    def test_rejects_unrelated_core_change(self):
        self.reject(lambda c:contact.mesh(c,contact.CORE)['vertices'][0].__setitem__(0,contact.mesh(c,contact.CORE)['vertices'][0][0]+.000001),'Unrelated mesh changed')

    def test_rejects_collision_change(self):
        self.reject(lambda c:c['hulls'][0]['vertices'][0].__setitem__(0,c['hulls'][0]['vertices'][0][0]+.000001),'runtime nodes/collision')

    def test_rejects_added_or_flipped_face(self):
        self.reject(lambda c:contact.mesh(c,contact.SPIKE)['faces'].__setitem__(0,tuple(reversed(self.spike['faces'][0]))),'Spike roots')


class NifContactTests(ContactTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'ARGS' not in globals() or not ARGS.nif:
            raise unittest.SkipTest('Actual NIF and pinned inspector must be provided')
        doc=json.loads(subprocess.check_output([str(ARGS.inspector.resolve()),str(ARGS.nif.resolve()),'--geometry']))
        cls.nif_shapes={m['name']:m for m in doc['shapes']}
        for name in (contact.CORE,contact.SPIKE):
            actual=cls.nif_shapes[name];cms=contact.mesh(cls.cms,name)
            assert np.array_equal(np.array(actual['triangles']),np.array(cms['faces']))
            assert np.allclose(np.array(actual['vertices'])/np.float32(69.99125),np.array(cms['vertices'])[:,:3],atol=3e-8,rtol=0)
            cms['vertices']=[list(p)+r[3:] for p,r in zip(np.array(actual['vertices'])/np.float32(69.99125),cms['vertices'])]
        cls.spike=contact.mesh(cls.cms,contact.SPIKE);cls.rows=np.array(cls.spike['vertices']);cls.faces=np.array(cls.spike['faces'])

    # NIF positions have their own float32 unit conversion. Test the actual
    # game-facing intersection instead of applying CMS byte identity tests.
    def test_nif_total_count_and_blood(self):
        self.assertEqual(sum(len(m['triangles']) for m in self.nif_shapes.values()),3996)
        self.assertEqual(len(self.nif_shapes['BloodFX']['triangles']),548)
        self.assertEqual(len(self.nif_shapes['BloodLighting']['triangles']),548)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--nif',type=Path);p.add_argument('--inspector',type=Path);ARGS=p.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContactTests)
    if ARGS.nif:
        for name in ('test_full_base_edges_inside_actual_triangle_surface','test_nif_total_count_and_blood'):
            suite.addTest(NifContactTests(name))
    result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
