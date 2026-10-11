"""Integration checks for the actual, pinned audit6 and reviewed visual ZIPs."""
import argparse
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Tools' / 'Blender'))
import package_unified_test as package


def archive(files):
    stream = io.BytesIO()
    with ZipFile(stream, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    return stream.getvalue()


def overlay_with(files):
    files = dict(files)
    checksum = 'SHA256SUMS_OPTIMIZED_TEST.txt'
    files[checksum] = ''.join(package.sha(data) + '  ' + name + '\n'
                              for name, data in sorted(files.items()) if name != checksum).encode()
    return archive(files)


class UnifiedPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ARGS.baseline_zip.read_bytes()
        cls.overlay = ARGS.overlay.read_bytes()
        cls.approved = json.loads(ARGS.inputs.read_text())
        cls.base_files = package.read_zip(cls.base)
        cls.visual_files = package.read_zip(cls.overlay)
        cls.files, cls.report = package.compose(cls.base, cls.overlay, cls.approved, 'a' * 40)

    def compose(self, *, base=None, overlay=None, approved=None):
        return package.compose(base if base is not None else self.base,
                               overlay if overlay is not None else self.overlay,
                               approved if approved is not None else self.approved, 'a' * 40)

    def test_every_deployed_game_byte_equals_prior_configuration(self):
        expected = package.game_files(self.base_files)
        expected.update(package.game_files(self.visual_files))
        self.assertEqual(package.game_files(self.files), expected)
        self.assertEqual(len(expected), 27)
        for name in (package.DLL, package.ESP, *[n for n in expected if n.endswith('.wav')]):
            self.assertEqual(self.files[name], self.base_files[name])
        changed = {name for name in expected if expected[name] != self.base_files[name]}
        self.assertEqual(changed, package.REPLACEMENTS)

    def test_metadata_describes_a_complete_test_mod(self):
        self.assertFalse(self.report['requires_separate_audit6_mod'])
        self.assertFalse(self.report['completed_release'])
        self.assertFalse(self.report['runtime_tested'])
        self.assertEqual(self.report['nif_total_triangles'], 3996)
        self.assertNotIn('README_OPTIMIZED_TEST_JA.txt', self.files)
        self.assertNotIn('DIAGNOSTIC_STATUS.md', self.files)
        self.assertEqual(self.files['LICENSES/HIGGS_GPL-3.0.txt'], self.base_files['LICENSES/HIGGS_GPL-3.0.txt'])
        for name, item in self.report['files'].items():
            self.assertEqual(package.sha(self.files[name]), item['sha256'])

    def test_deterministic_zip_and_all_file_checksums(self):
        scratch = ROOT / 'build' / 'unified-package-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            a, b = Path(tmp) / 'a.zip', Path(tmp) / 'b.zip'
            package.write_zip(a, self.files)
            package.write_zip(b, self.files)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(package.read_zip(a.read_bytes()), self.files)

    def test_rejects_a_different_baseline(self):
        with self.assertRaisesRegex(ValueError, 'Wrong audit6 baseline'):
            self.compose(base=self.base + b'changed')

    def test_rejects_runtime_files_in_visual_input(self):
        files = dict(self.visual_files)
        files[package.DLL] = self.base_files[package.DLL]
        with self.assertRaisesRegex(ValueError, 'only five visual assets'):
            self.compose(overlay=overlay_with(files))

    def test_rejects_unapproved_visual_even_with_recomputed_checksums(self):
        files = dict(self.visual_files)
        files[package.NIF] += b'changed'
        with self.assertRaisesRegex(ValueError, 'Unapproved visual asset'):
            self.compose(overlay=overlay_with(files))

    def test_rejects_missing_game_asset(self):
        files = dict(self.visual_files)
        del files[package.NIF]
        with self.assertRaisesRegex(ValueError, 'only five visual assets'):
            self.compose(overlay=overlay_with(files))

    def test_rejects_false_triangle_or_runtime_preservation_proof(self):
        for key, value in [('nif_total_triangles', 4001), ('nodes_and_collision_bytes_preserved', False)]:
            files = dict(self.visual_files)
            proof = json.loads(files['OPTIMIZED_VISUAL_PROVENANCE.json'])
            proof[key] = value
            files['OPTIMIZED_VISUAL_PROVENANCE.json'] = json.dumps(proof).encode()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.compose(overlay=overlay_with(files))

    def test_rejects_changed_approval_contract(self):
        approved = copy.deepcopy(self.approved)
        approved['game_files'][package.DLL] = package.sha(self.base_files[package.DLL])
        with self.assertRaisesRegex(ValueError, 'Approved replacement set changed'):
            self.compose(approved=approved)

    def test_rejects_unsafe_and_case_colliding_zip_paths(self):
        for files in ({'../escape': b'x'}, {'C:/escape': b'x'},
                      {'meshes/x': b'x', 'Meshes/X': b'y'}):
            with self.subTest(files=list(files)), self.assertRaises(ValueError):
                package.read_zip(archive(files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-zip', 'overlay', 'inputs'):
        parser.add_argument('--' + name, type=Path, required=True)
    ARGS = parser.parse_args()
    unittest.main(argv=[sys.argv[0], '-v'])
