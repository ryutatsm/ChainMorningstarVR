"""Classification boundaries; fixtures contain no real user logs."""
import unittest
from classify_existing_logs import classify, EXE_MD5, TEARDOWN_FRAMES


def fixture(frames=TEARDOWN_FRAMES, md5=EXE_MD5, marker='P', register='0x220'):
    return ('Unhandled exception "EXCEPTION_ACCESS_VIOLATION" at 0x1 SkyrimVR.exe+014339F\n'
            f'Executable MD5: {md5}\n'
            'Process Uptime: 00:00:40 (40000ms)\nCALL STACK:\n' +
            ''.join(f' [{i}][{marker}] 0x1 SkyrimVR.exe+{offset:X}\n' for i, offset in enumerate(frames)) +
            f'REGISTERS:\n RDI {register}\nSTACK:\n ChainMorningstarVR.dll\n'
            'MODULES:\n SkyrimVR.exe\nSKSE PLUGINS:\n').encode()


class ClassifierTests(unittest.TestCase):
    def test_complete_teardown_chain(self):
        row = classify(fixture(), 'test.log')
        self.assertEqual(row['category'], 'actor_shadow_scene_null_during_teardown')
        self.assertFalse(row['manual_exit_proven_by_log'])
        self.assertFalse(row['root_cause_mod_identified'])

    def test_fault_offset_without_teardown_is_not_enough(self):
        self.assertEqual(classify(fixture(frames=TEARDOWN_FRAMES[:3]), 'test.log')['category'], 'unclassified')

    def test_stack_scan_is_not_unwind_evidence(self):
        self.assertEqual(classify(fixture(marker='S'), 'test.log')['category'], 'unclassified')

    def test_other_executable_is_not_offset_matched(self):
        self.assertEqual(classify(fixture(md5='0' * 32), 'test.log')['category'], 'unclassified')

    def test_other_fault_address_is_not_null_scene_claim(self):
        self.assertEqual(classify(fixture(register='0x12345678'), 'test.log')['category'], 'unclassified')

    def test_module_presence_comes_only_from_module_list(self):
        data = fixture()
        self.assertFalse(classify(data, 'test.log')['cms_module_listed'])
        loaded = data.replace(b'MODULES:\n', b'MODULES:\n ChainMorningstarVR.dll 0x1000\n')
        self.assertTrue(classify(loaded, 'test.log')['cms_module_listed'])
        missing = data.split(b'MODULES:', 1)[0]
        self.assertIsNone(classify(missing, 'test.log')['cms_module_listed'])

    def test_mist_menu_path_does_not_infer_mod_from_form_annotation(self):
        data = fixture(frames=[0x534D71, 0x8DA726, 0xF1BA95])
        data = data.replace(b'SkyrimVR.exe+014339F', b'SkyrimVR.exe+0534D71')
        data = data.replace(b'RDI 0x220', b'RAX 0x14 (FormID 0x14 -> PlayerCharacter)')
        row = classify(data, 'test.log')
        self.assertEqual(row['category'], 'mist_menu_vr_scene_render_path')
        self.assertEqual(row['fault_base_value'], '0x14')
        self.assertFalse(row['root_cause_mod_identified'])


if __name__ == '__main__':
    unittest.main()
