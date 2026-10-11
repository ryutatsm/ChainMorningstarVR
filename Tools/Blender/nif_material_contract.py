"""In-place lighting-only patch for the reviewed 3996-triangle SSE NIF.

No serialization, reordering or geometry generation: only three shader fields
may change. The entire input identity, layout and protected blocks are checked.
"""
import hashlib
import struct

INPUT_SHA256 = 'dfabd8dd383eb063bc3f61a4af0cde7a3760badef9e79d386b82125318ca2e65'
SOURCE_PROFILES = {'spike-contact': INPUT_SHA256,
                   'previous-leather-edge': 'a2f5a40473884201c1eac9257f12d81a973d918d84d403ef8b914af36bc8d2c9'}
OWN_EMIT = 1 << 22
ENVMAP_LIGHT_FADE = 1 << 15


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def read(self, fmt):
        size = struct.calcsize('<' + fmt)
        require(self.pos + size <= len(self.data), 'Truncated NIF')
        value = struct.unpack_from('<' + fmt, self.data, self.pos)
        self.pos += size
        return value[0] if len(value) == 1 else value

    def string(self, fmt='I'):
        length = self.read(fmt)
        require(self.pos + length <= len(self.data), 'Truncated NIF string')
        value = self.data[self.pos:self.pos + length]
        self.pos += length
        return value.decode('utf-8').rstrip('\0')


def parse(data):
    require(data.startswith(b'Gamebryo File Format, Version 20.2.0.7\n'), 'Unsupported NIF header')
    r = Reader(data, data.index(b'\n') + 1)
    version, endian, user, count, stream = r.read('IBIII')
    require((version, endian, user, stream) == (0x14020007, 1, 12, 100), 'Expected Skyrim SE/VR NIF')
    require(0 < count < 10000, 'Invalid NIF block count')
    for _ in range(3):
        r.string('B')
    types = [r.string() for _ in range(r.read('H'))]
    indices = [r.read('H') for _ in range(count)]
    sizes = [r.read('I') for _ in range(count)]
    nstrings, maximum = r.read('II')
    require(nstrings < 10000 and maximum < 10000, 'Invalid NIF strings')
    strings = [r.string() for _ in range(nstrings)]
    for _ in range(r.read('I')):
        r.read('I')
    start = r.pos
    blocks = []
    for index, size in zip(indices, sizes):
        require(index < len(types) and size > 0 and r.pos + size <= len(data), 'Invalid NIF block layout')
        blocks.append(dict(type=types[index], offset=r.pos, size=size))
        r.pos += size
    require(len(data) - r.pos == 8 and struct.unpack_from('<II', data, r.pos) == (1, 0), 'Unexpected NIF root/footer')
    return dict(blocks=blocks, strings=strings, header_end=start, footer_start=r.pos)


def textures(data, block):
    r = Reader(data, block['offset'])
    paths = [r.string() for _ in range(r.read('I'))]
    require(r.pos == block['offset'] + block['size'] and len(paths) == 9, 'Unexpected texture-set layout')
    return paths


def materials(data):
    nif = parse(data)
    rows = []
    for i, block in enumerate(nif['blocks']):
        if block['type'] != 'BSLightingShaderProperty':
            continue
        off = block['offset']
        kind, name, extras, controller = struct.unpack_from('<4I', data, off)
        require(kind in (0, 1) and extras == 0 and controller == 0xffffffff, 'Unexpected shader controller/layout')
        require(name == 0xffffffff and block['size'] == (104 if kind == 1 else 100), 'Unexpected material layout')
        tex = struct.unpack_from('<I', data, off + 40)[0]
        require(tex < len(nif['blocks']) and nif['blocks'][tex]['type'] == 'BSShaderTextureSet', 'Invalid texture reference')
        paths = textures(data, nif['blocks'][tex])
        flags1, flags2 = struct.unpack_from('<II', data, off + 16)
        emissive = struct.unpack_from('<3f', data, off + 44)
        multiple = struct.unpack_from('<f', data, off + 56)[0]
        rows.append(dict(block=i, offset=off, type=kind, flags1=flags1, flags2=flags2,
                         emissive=list(emissive), emissive_multiple=multiple, textures=paths))
    return nif, rows


def patch(data, profile='spike-contact'):
    require(profile in SOURCE_PROFILES and sha(data) == SOURCE_PROFILES[profile], 'Unapproved lighting source NIF')
    nif, rows = materials(data)
    require(len(rows) == 32, 'Expected 31 visible lighting materials and one protected blood material')
    result = bytearray(data)
    changes = []
    for row in rows:
        if row['textures'][0].lower().startswith('textures\\blood\\'):
            continue
        require(row['textures'][0].startswith('textures\\weapons\\ChainMorningstarVR\\cms_'), 'Unexpected visible material')
        require(row['emissive'] == [0., 0., 0.] and row['emissive_multiple'] == 1., 'Source emission contract changed')
        require(not row['flags1'] & OWN_EMIT and not row['flags2'] & ENVMAP_LIGHT_FADE, 'Source flags changed')
        off = row['offset']
        struct.pack_into('<II', result, off + 16, row['flags1'] | OWN_EMIT, row['flags2'] | ENVMAP_LIGHT_FADE)
        struct.pack_into('<f', result, off + 56, 0.)
        changes.append(dict(block=row['block'], diffuse=row['textures'][0],
                            before_flags1=row['flags1'], after_flags1=row['flags1'] | OWN_EMIT,
                            before_flags2=row['flags2'], after_flags2=row['flags2'] | ENVMAP_LIGHT_FADE,
                            emissive_rgb=[0, 0, 0], before_emissive_multiple=1, after_emissive_multiple=0))
    require(len(changes) == 31, 'Not all visible materials were covered')
    result = bytes(result)
    updated, new_rows = materials(result)
    require(updated == nif, 'NIF layout/header changed')
    changed_ids = {c['block'] for c in changes}
    for i, block in enumerate(nif['blocks']):
        a, b = block['offset'], block['offset'] + block['size']
        if i not in changed_ids:
            require(data[a:b] == result[a:b], 'Protected NIF block changed')
    allowed = set()
    for row in rows:
        if row['block'] in changed_ids:
            allowed.update(range(row['offset'] + 16, row['offset'] + 24))
            allowed.update(range(row['offset'] + 56, row['offset'] + 60))
    changed_bytes = {i for i, (a, b) in enumerate(zip(data, result)) if a != b}
    require(changed_bytes <= allowed and len(data) == len(result), 'Non-material bytes changed')
    proof = dict(format='cms-nif-dark-lighting-v1', input_nif_sha256=sha(data), output_nif_sha256=sha(result),
                 source_profile=profile,
                 visible_materials=31, changed_bytes=len(changed_bytes), changes=changes,
                 geometry_uv_normals_tangents_nodes_collision_blood_byte_identical=True,
                 diffuse_normal_specular_environment_textures_unchanged=True,
                 glossiness_specular_strength_environment_scale_unchanged=True,
                 runtime_validated=False)
    return result, proof
