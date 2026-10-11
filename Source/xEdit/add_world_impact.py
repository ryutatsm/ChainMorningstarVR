"""Append only SNDR 805 to the verified custom audit6 ESP; keep old records raw.

Clone our existing spatial non-looping 804, changing EDID/ANAM/FormID only.
No vanilla export is required and no weapon/inventory records are rebuilt.
"""
from pathlib import Path
import hashlib,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_plugin import parse_record,encode_record

BASE_SHA='b968bae79e6a2c412185115bcff03554ff00ae52c1a097f0b36502fe5327d24a'
def append_impact(raw):
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise ValueError('Wrong approved audit6 ESP')
    header_size=24+struct.unpack_from('<I',raw,4)[0]
    header=parse_record(raw[:header_size]); at=header_size; groups=[];template=None
    while at<len(raw):
        assert raw[at:at+4]==b'GRUP';size=struct.unpack_from('<I',raw,at+4)[0]
        group=raw[at:at+size];assert len(group)==size and size>=24
        if group[8:12]==b'SNDR':
            pos=24
            while pos<size:
                n=24+struct.unpack_from('<I',group,pos+4)[0];record=parse_record(group[pos:pos+n])
                if record.form_id==0x01000804:template=record
                pos+=n
            assert pos==size
        groups.append(group);at+=size
    assert at==len(raw) and template is not None and template.field(b'LNAM')[1]&0x38==0
    fields=[(tag,b'CMS_HeavyIronImpact\0' if tag==b'EDID' else
             b'fx\\ChainMorningstarVR\\iron_impact.wav\0' if tag==b'ANAM' else value)
            for tag,value in template.fields]
    addition=encode_record(b'SNDR',0x01000805,fields)
    result=[]
    for group in groups:
        if group[8:12]==b'SNDR':
            group=group[:4]+struct.pack('<I',len(group)+len(addition))+group[8:]+addition
        result.append(group)
    fields=[]
    for tag,value in header.fields:
        if tag==b'HEDR':
            version,count,next_id=struct.unpack('<fII',value);assert(count,next_id)==(8,0x805)
            value=struct.pack('<fII',version,count+1,0x806)
        fields.append((tag,value))
    return encode_record(b'TES4',0,fields)+b''.join(result)
