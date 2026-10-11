import hashlib,importlib.util,io,struct,sys,unittest,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'Tools'),str(ROOT/'Source/Audio'),str(ROOT/'Source/xEdit'),str(ROOT/'Tests')]
from package_world_impact_test import BASE,BASE_SHA,read_zip,verify_sums,append_impact,verify_dll
from generate_world_impact import synthesize,SOURCE,SOURCE_SHA256,read_pcm
from test_plugin_binary import inspect_binary

def record_bytes(raw):
    records={};at=0
    while at<len(raw):
        if raw[at:at+4]==b'GRUP':at+=24;continue
        size=24+int.from_bytes(raw[at+4:at+8],'little');key=(raw[at:at+4],int.from_bytes(raw[at+12:at+16],'little'))
        records[key]=raw[at:at+size];at+=size
    assert at==len(raw);return records

class WorldImpactAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==BASE_SHA
        cls.files=read_zip(raw);verify_sums(cls.files,'SHA256SUMS.txt')
        cls.esp=cls.files['ChainMorningstarVR.esp']
    def test_old_records_raw_byte_identical(self):
        new=record_bytes(append_impact(self.esp));old=record_bytes(self.esp)
        self.assertEqual(set(new),set(old)|{(b'SNDR',0x01000805)})
        for key in old:
            if key!=(b'TES4',0):self.assertEqual(new[key],old[key])
    def test_header_and_spatial_sound_fields(self):
        records,groups=inspect_binary(append_impact(self.esp));self.assertEqual(groups,[b'STAT',b'WEAP',b'SNDR'])
        self.assertEqual(struct.unpack('<fII',records[(b'TES4',0)][b'HEDR'])[1:],(9,0x806))
        new=records[(b'SNDR',0x01000805)];old=records[(b'SNDR',0x01000804)]
        self.assertEqual(new[b'ANAM'],b'fx\\ChainMorningstarVR\\iron_impact.wav\0')
        self.assertEqual(new[b'EDID'],b'CMS_HeavyIronImpact\0')
        for tag in old:
            if tag not in (b'ANAM',b'EDID'):self.assertEqual(new[tag],old[tag])
        self.assertEqual(new[b'LNAM'][1]&0x38,0)
    def test_reject_unapproved_esp(self):
        with self.assertRaises(ValueError):append_impact(self.esp[:-1])
    def test_selected_wave_reproducible_and_attenuated_only(self):
        data,report=synthesize();self.assertEqual(data,synthesize()[0])
        self.assertEqual(report['sha256'],'48fc4e54b6a4f5dd3a9de3c0f286a15350b5cdc471a8c9325cfba2ef95b8e455')
        source=SOURCE.read_bytes();self.assertEqual(hashlib.sha256(source).hexdigest(),SOURCE_SHA256)
        original=read_pcm(source);actual=read_pcm(data)
        # The user's chosen timbre must survive exactly: a single linear gain,
        # with no regenerated noise, normalization, speed or envelope change.
        np.testing.assert_array_equal(actual,np.rint(original.astype(float)*.85).astype('<i2'))
        self.assertEqual(report['sample_number'],5);self.assertEqual(report['gain'],.85)
        self.assertGreater(report['power_below_700hz'],.8)
        self.assertLess(report['power_below_140hz'],.25)
        self.assertGreater(report['power_700_to_3500hz'],.12)
        self.assertLess(report['peak'],.60)
        self.assertEqual(report['seconds'],.85)
        with wave.open(io.BytesIO(data),'rb') as w:self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(1,2,44100))
    def test_old_audio_and_successful_nif_identity(self):
        expected={'iron_scrape.wav':'b6309ee4a9142198e44282ce02f48f379b2c66a8d0f55e3e66accf7b6fcce69c',
                  'air_cut.wav':'4e5e618972211ad2a80c251c6c46d0caeed001aa401a881a168382bbacd7d231',
                  'disarm_strike.wav':'c87360f323130eca98f034cffb188f7b9c17fb006ac651afc6f2b04a2d8b3e0f'}
        for name,digest in expected.items():self.assertEqual(hashlib.sha256(self.files['sound/fx/ChainMorningstarVR/'+name]).hexdigest(),digest)
        self.assertEqual(hashlib.sha256(self.files['meshes/weapons/ChainMorningstarVR/ChainMorningstar.nif']).hexdigest(),'8d07faf527074902495386f0e9c8a2b8e53ffd8b0e9d33f27c401f8656a2302f')
    def test_old_dll_cannot_be_labeled_new_audio(self):
        with self.assertRaises(ValueError):verify_dll(self.files['SKSE/Plugins/ChainMorningstarVR.dll'])
if __name__=='__main__':unittest.main()
