"""Lighting-only changes must preserve all authored geometry and runtime bytes."""
import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Tools' / 'Blender'))
import nif_material_contract as material
import package_lighting_test as lighting
import package_unified_test as unified


class LightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = ARGS.nif.read_bytes()
        cls.after, cls.proof = material.patch(cls.before)

    def test_every_other_block_and_header_footer_is_byte_identical(self):
        nif = material.parse(self.before)
        changed = {c['block'] for c in self.proof['changes']}
        self.assertEqual(self.before[:nif['header_end']], self.after[:nif['header_end']])
        self.assertEqual(self.before[nif['footer_start']:], self.after[nif['footer_start']:])
        self.assertEqual(len(changed), 31)
        for i, block in enumerate(nif['blocks']):
            if i in changed:
                continue
            lo, hi = block['offset'], block['offset'] + block['size']
            self.assertEqual(self.before[lo:hi], self.after[lo:hi], block['type'])

    def test_protected_blood_and_all_texture_sets_are_unchanged(self):
        nif, rows = material.materials(self.before)
        blood = [r for r in rows if r['textures'][0].lower().startswith('textures\\blood\\')]
        self.assertEqual(len(blood), 1)
        protected = {r['block'] for r in blood}
        protected.update(i for i,b in enumerate(nif['blocks']) if b['type'] in ('BSEffectShaderProperty', 'BSShaderTextureSet'))
        for i in protected:
            block = nif['blocks'][i];lo,hi=block['offset'],block['offset']+block['size']
            self.assertEqual(self.before[lo:hi], self.after[lo:hi])

    def test_pinned_nifly_reads_all_material_changes_and_only_those_fields(self):
        scratch = ROOT / 'build' / 'lighting-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            after = Path(tmp) / 'after.nif';after.write_bytes(self.after)
            before_doc = lighting.inspect(ARGS.nif, ARGS.inspector)
            after_doc = lighting.inspect(after, ARGS.inspector)
            lighting.verify_inspections(before_doc, after_doc)
            self.assertEqual(after_doc['node_count'], 22)
            self.assertEqual(len(after_doc['shapes']), 33)

    def test_deterministic_output_identity(self):
        self.assertEqual(material.patch(self.before), (self.after, self.proof))
        self.assertEqual(material.sha(self.after), '667c88138d3572b4057dc6792c9d1569e2cae09fd08a89d53d751f37122ca01c')
        self.assertEqual(len(self.before), len(self.after))
        self.assertEqual(self.proof['changed_bytes'], 124)

    def test_rejects_other_or_corrupted_input(self):
        for data in (b'not a NIF', self.before[:-1], self.before + b'changed'):
            with self.subTest(size=len(data)), self.assertRaisesRegex(ValueError, 'Unapproved lighting source'):
                material.patch(data)

    def test_rejects_accidental_double_application(self):
        with self.assertRaisesRegex(ValueError, 'Unapproved lighting source'):
            material.patch(self.after)

    def test_full_package_diff_is_only_the_nif(self):
        source = unified.game_files(unified.read_zip(ARGS.previous_zip.read_bytes()))
        corrected = unified.read_zip(ARGS.lighting_zip.read_bytes())
        actual = unified.game_files(corrected)
        self.assertEqual(set(source), set(actual))
        self.assertEqual(len(actual), 27)
        self.assertEqual({n for n in source if source[n] != actual[n]}, {unified.NIF})
        self.assertEqual(actual[unified.NIF], self.after)
        unified.verify_sums(corrected, 'SHA256SUMS.txt')
        unified.runtime_checks(corrected)
        report = json.loads(corrected['BUILD_PROVENANCE.json'])
        self.assertFalse(report['requires_separate_audit6_mod'])
        self.assertFalse(report['runtime_tested'])
        self.assertFalse(report['completed_release'])
        self.assertEqual(report['nif_total_triangles'], 3996)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nif', 'inspector', 'previous-zip', 'lighting-zip'):
        parser.add_argument('--' + name, type=Path, required=True)
    ARGS = parser.parse_args()
    unittest.main(argv=[sys.argv[0], '-v'])
