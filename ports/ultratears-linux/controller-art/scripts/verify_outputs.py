"""Check exported coordinates and output sizes; encode previews using stdlib only."""
from pathlib import Path
import json
import hashlib
import math
import struct
import subprocess
import zlib

root = Path(__file__).resolve().parents[1]
actual = subprocess.check_output([str(root/'build/render_deck'), '--anchors'])
anchors = json.loads(actual)
expected = json.loads((root/'anchors.json').read_text())
assert anchors == expected
assert anchors['front_offset'] == [2, 26]
assert (anchors['front']['width'], anchors['front']['height']) == (580, 340)
assert {a['label']: a['pixel'] for a in anchors['front']['anchors'] if a['id'].startswith('face_')} == {
    'A': [519,132], 'B': [537,115], 'X': [501,115], 'Y': [519,97]}
front_controls={a['id']:a['pixel'] for a in anchors['front']['anchors']}
assert front_controls['left_stick']==[90,114] and front_controls['right_stick']==[472,114]
assert front_controls['dpad_center']==[40,105]
assert front_controls['left_stick'][1]-front_controls['dpad_center'][1]==9
def chunk(kind, data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
assert anchors['schema'] == 2
source = {a['id']: a for a in anchors['front']['anchors']}
for a in anchors['inclined']['anchors']:
    if a['source'] is None:
        assert a['id'] in ('left_trigger','right_trigger','left_bumper','right_bumper')
        continue
    assert source[a['id']]['source'] == a['source']
    x, y = a['source']
    assert math.isclose(a['pixel'][0],290+(x-288)*(0.94+0.04*y/288),abs_tol=1e-12)
    assert a['pixel'][1] == 72+0.75*y
for name in ('front', 'inclined'):
    face = {a['label']: a['pixel'] for a in anchors[name]['anchors'] if a['id'].startswith('face_')}
    assert face['Y'][1] < face['X'][1] < face['A'][1]
    assert face['X'][0] < face['Y'][0] < face['B'][0]
assert len(anchors['resource_mapping']) == 6
for resource, view in anchors['resource_mapping'].items():
    assert view == ('inclined' if resource.endswith('1^w') else 'front')
for name in ('front', 'inclined', 'top'):
    spec = anchors[name]
    w, h = spec['width'], spec['height']
    raw = (root/'build'/f'{name}.rgba').read_bytes()
    assert len(raw) == w*h*4
    baseline=(root/'build/reference'/f'{name}.rgba').read_bytes()
    baseline_hashes={'front':'bd99b460eb5ca670844004d9e3269f9cac751788b81b32c7aad118dd2de934e3',
                     'inclined':'1969f6250eb4fe05cc38770c28f36ec68d42864e16038dc42c3a6bb4b93dd379',
                     'top':'9915cdc7034896ee29f250c7f28ff3885bcbda4c4c921d2422d74d125eeffa1f'}
    assert hashlib.sha256(baseline).hexdigest()==baseline_hashes[name]
    assert len(baseline)==len(raw)
    changed=[];outside=0
    for y in range(h):
        for x in range(w):
            at=(y*w+x)*4
            if raw[at:at+4]==baseline[at:at+4]:continue
            changed.append([x,y])
            if name=='front':
                allowed=20<=x<60 and 71<=y<125
            elif name=='inclined':
                # Exact 2x2 inverse-sampling support may touch changed source
                # pixels only in the old/new D-pad source box [18,45,58,99).
                sy=(y+0.5-72)/0.75
                sx=(x+0.5-290)/(0.94+0.04*sy/288)+288
                ix,iy=math.floor(sx-0.5),math.floor(sy-0.5)
                allowed=ix+1>=18 and ix<58 and iy+1>=45 and iy<99
            else:allowed=False
            outside+=not allowed
    assert outside==0,f'{name}: {outside} pixels changed outside allowed region'
    assert bool(changed)==(name!='top')
    diff={'view':name,'changed_pixels':len(changed),'outside_allowed_region':outside,
          'changed_bounds_half_open':([min(p[0] for p in changed),min(p[1] for p in changed),
                                       max(p[0] for p in changed)+1,max(p[1] for p in changed)+1] if changed else None),
          'baseline_sha256':baseline_hashes[name],'output_sha256':hashlib.sha256(raw).hexdigest()}
    (root/'build'/f'{name}-pixel-diff.json').write_text(json.dumps(diff,indent=2)+'\n')
    assert any(0 < a < 255 for a in raw[3::4])
    for a in spec['anchors']:
        assert 0 <= a['pixel'][0] < w
        assert 0 <= a['pixel'][1] < h
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',w,h,8,6,0,0,0))
    png += chunk(b'IDAT',zlib.compress(b''.join(b'\0'+raw[y*w*4:(y+1)*w*4] for y in range(h))))
    png += chunk(b'IEND',b'')
    (root/'build'/f'{name}.png').write_bytes(png)
    print(f'{name}: {w}x{h}, {len(raw)} bytes, RGBA8 PNG generated PASS')
print('Exported C anchors equal anchors.json; Xbox A/B/X/Y exact coordinates PASS')
print('Front/inclined changes restricted to D-pad footprint; all other pixels exact; top unchanged PASS')
