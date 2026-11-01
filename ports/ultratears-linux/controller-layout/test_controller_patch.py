#!/usr/bin/env python3
"""Integration tests with explicitly supplied private fixtures; no bundled game data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--anchors',type=Path,required=True)
    p.add_argument('--reference-patch',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();work=args.work.resolve();assert not work.exists()
    meta=json.loads(args.metadata.read_text());assert not work.is_relative_to(Path(meta['root']).resolve())
    work.mkdir(parents=True);checks=[]
    common=[sys.executable,'-B',str(HERE/'build_controller_patch.py'),'--metadata',str(args.metadata),'--anchors',str(args.anchors)]
    def command(name,cmd,success,needle=None):
        r=subprocess.run(cmd,capture_output=True,text=True)
        assert (r.returncode==0)==success,(name,r.stdout,r.stderr)
        if needle:assert needle in r.stdout+r.stderr,(name,r.stdout,r.stderr)
        checks.append(dict(name=name,passed=True,exit_code=r.returncode))
    repeat=work/'repeat'
    command('deterministic-full-build',common+['--output',str(repeat)],True)
    for entry in meta['members']:
        name=entry['name']
        if name.endswith(('.bflyt','.bflan')):assert (repeat/name).read_bytes()==(args.reference_patch/name).read_bytes()
    command('existing-output-refused',common+['--output',str(repeat)],False,'Output must be a new directory')
    d=json.loads(args.anchors.read_text());d['anchors'][0]['pixel'][0]=d['width']+1;bad=work/'out-of-canvas.json'
    with bad.open('x') as f:json.dump(d,f)
    command('out-of-canvas-refused',common+['--anchors',str(bad),'--output',str(work/'rejected-canvas')],False,'outside renderer canvas')
    d=json.loads(args.anchors.read_text());d['anchors']=[a for a in d['anchors'] if a['id']!='left_trigger'];bad=work/'missing-one-shoulder.json'
    with bad.open('x') as f:json.dump(d,f)
    command('missing-anchor-refused',common+['--anchors',str(bad),'--output',str(work/'rejected-missing')],False,'All ten groups are required')
    d=json.loads(args.anchors.read_text());d['anchors'][0]['pixel'][0]+=.1;bad=work/'pixel-authoritative.json'
    with bad.open('x') as f:json.dump(d,f)
    command('authoritative-pixel-update-accepted',common+['--anchors',str(bad),'--output',str(work/'check-pixel'),'--check-only'],True)
    d=json.loads(args.anchors.read_text());d.pop('transform',None);d['view']='custom-renderer';d['width']*=2;d['height']*=2
    for a in d['anchors']:
        a.pop('source',None);a['pixel']=[v*2 for v in a['pixel']]
        if a['id'].startswith('face_'):a['coverage_radius']=20
        if a['id']=='dpad_center':a['coverage_radius']=38
    bad=work/'renderer-independent.json'
    with bad.open('x') as f:json.dump(d,f)
    command('arbitrary-canvas-no-source-full-verification',common+['--anchors',str(bad),'--output',str(work/'custom-renderer-patch')],True)
    assert json.loads((work/'custom-renderer-patch/verification.json').read_text())['passed']
    d=json.loads(args.anchors.read_text());d['transform']['x']="__import__('os').getcwd()";bad=work/'unsafe-projection.json'
    with bad.open('x') as f:json.dump(d,f)
    command('executable-projection-refused',common+['--anchors',str(bad),'--output',str(work/'rejected-expression')],False,'Projection accepts')
    bad=work/'bad-source-sha.json';d=json.loads(args.metadata.read_text());d['members'][0]['sha256']='0'*64
    with bad.open('x') as f:json.dump(d,f)
    command('source-sha-refused',common+['--metadata',str(bad),'--output',str(work/'rejected-sha')],False,'AssertionError')
    command('optimized-python-refused',[sys.executable,'-O','-B',str(HERE/'build_controller_patch.py')]+common[3:]+['--output',str(work/'rejected-optimized')],False,'Do not run this validator with Python -O')
    # Tamper cloned outputs only: independent geometry and byte allowlists must reject.
    def clone(name):
        dest=work/name;shutil.copytree(repeat,dest);(dest/'verification.json').unlink();return dest
    def refresh_modified_hashes(dest):
        file=dest/'manifest.json';d=json.loads(file.read_text())
        for record in d['files']:
            data=(dest/record['name']).read_bytes();record['patch_sha256']=hashlib.sha256(data).hexdigest();record['patch_bytes']=len(data);record['changed']=record['patch_sha256']!=record['original_sha256']
        file.write_text(json.dumps(d))
    bad=clone('bad-marker');mf=json.loads((bad/'manifest.json').read_text());entry=next(x for x in mf['static_writes'] if x['pane']=='P_CircleZL_00' and x['property']=='translation_x');file=bad/'blyt/PaSystemController_00.bflyt';data=bytearray(file.read_bytes());struct.pack_into('<f',data,entry['offset'],entry['after']+2.);file.write_bytes(data)
    # Also corrupt the active animation value, so the static value cannot be masked by Pattern.
    import importlib.util
    spec=importlib.util.spec_from_file_location('reader',HERE/'resource_layout.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    file=bad/'anim/PaSystemController_00_Pattern.bflan';data=bytearray(file.read_bytes());anim=reader.parse_animation(bytes(data));entry=next(e for e in anim['entries'] if e['name']=='P_CircleZL_00');ch=next(c for c in entry['channels'] if c['property']=='translation_x')
    for k in ch['keys']:struct.pack_into('<f',data,k['value_offset'],k['value']+2.)
    file.write_bytes(data)
    refresh_modified_hashes(bad)
    command('marker-misalignment-refused',[sys.executable,'-B',str(HERE/'verify_controller_patch.py'),str(bad)],False,'AssertionError')
    bad=clone('bad-onoff');file=bad/'anim/PaSystemController_00_OnOff_L.bflan';data=bytearray(file.read_bytes());data[95]^=1;file.write_bytes(data)
    refresh_modified_hashes(bad)
    command('unrelated-onoff-byte-refused',[sys.executable,'-B',str(HERE/'verify_controller_patch.py'),str(bad)],False,'AssertionError')
    assert all(not (work/n).exists() for n in ['rejected-canvas','rejected-missing','rejected-expression','rejected-sha','rejected-optimized','check-pixel'])
    result=dict(passed=True,game_data_bundled=False,resource_reproducibility=True,arbitrary_renderer_full_verification=True,checks=checks)
    with (work/'tests.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
