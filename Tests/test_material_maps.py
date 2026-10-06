"""Regression checks for tangent direction and non-opacity normal-map alpha."""
from pathlib import Path
import importlib.util
import io
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def load_source(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

textures=load_source('texture_source','Source/Textures/generate_textures.py')
dds=load_source('texture_encoder','Source/Textures/encode_dds.py')


def last_mip(path):
    """Decode the 1 x 1 mip independently from encoder internals."""
    raw=path.read_bytes();header=bytearray(raw[:128])
    assert struct.unpack_from('<I',raw,28)[0]==11
    struct.pack_into('<I',header,12,1);struct.pack_into('<I',header,16,1)
    struct.pack_into('<I',header,20,16);struct.pack_into('<I',header,28,1)
    struct.pack_into('<I',header,108,0x1000)
    return np.asarray(Image.open(io.BytesIO(header+raw[-16:])).convert('RGBA'))[0,0]


class MaterialMapTests(unittest.TestCase):
    def test_analytic_height_gradient_uses_original_v_up(self):
        # A height that rises right/down must lean normal left/toward original +V.
        y,x=np.mgrid[:1024,:1024].astype(np.float32)
        n=textures.normal_from_height((x+y)*.15,(1024,1024))
        center=n[512,512].astype(float)/127.5-1
        expected=np.array([-.15,.15,1]);expected/=np.linalg.norm(expected)
        np.testing.assert_allclose(center,expected,atol=.008)

    def test_nif_green_is_inverted_exactly_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'direction_n.png'
            pixels=np.empty((1024,1024,4),np.uint8);pixels[:]=[127,183,242,96]
            Image.fromarray(pixels).save(path)
            result=dds.encode(path)
            decoded=np.asarray(Image.open(path.with_suffix('.dds')).convert('RGBA'))[512,512]
            self.assertLess(decoded[1],100)
            self.assertGreater(decoded[2],230)
            self.assertLess(last_mip(path.with_suffix('.dds'))[1],100)
            self.assertTrue(result['normal_green_inverted_for_nif'])
            self.assertEqual(result['decoded_mips'],11)

    def test_mip_normals_are_not_weighted_by_specular_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'specular_n.png'
            pixels=np.empty((1024,1024,4),np.uint8)
            pixels[:,::2]=[64,127,238,16]
            pixels[:,1::2]=[191,127,238,180]
            Image.fromarray(pixels).save(path)
            dds.encode(path)
            final=last_mip(path.with_suffix('.dds')).astype(int)
            # Both opposed normals have equal area. Gloss must not bias their
            # mean toward the brighter-alpha side as RGBA filtering used to do.
            self.assertLess(abs(final[0]-127),7)
            self.assertGreater(final[2],246)
            self.assertLess(abs(final[3]-98),4)


if __name__=='__main__':
    unittest.main()
