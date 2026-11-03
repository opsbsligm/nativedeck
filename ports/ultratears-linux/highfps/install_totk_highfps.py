"""Preserve live-profile saves and the old ELF; atomically install timing build."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

root=Path.home()/'native-recomp'
bundle=root/'ultratears/releases/v143-20261031-first'
report=root/'evidence/library-unlock-20261103'
backup=report/'backup'
candidate=root/'work/totk-1.4.3-20261031/highfps-20261103'
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert (candidate/'prepare.json').is_file() and (candidate/'ultratears').stat().st_size>500*1024**2
assert shutil.disk_usage(root).free>2*1024**3
sys.path.insert(0,str(root/'swr'))
from botw_launch import save_inventory,backup_saves
unit='nd-totk-v143-first-boot-20261031'
pid=int(subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','--value'],text=True))
assert pid>0 and Path('/proc',str(pid),'exe').resolve()==bundle/'ultratears'
env=dict(x.decode().split('=',1) for x in Path('/proc',str(pid),'environ').read_bytes().split(b'\0') if b'=' in x)
profile=Path(env['XDG_DATA_HOME'])/'ultratears/userdata'
assert profile==Path.home()/'.local/share/ultratears/test-profiles/v8-opening-20261102/ultratears/userdata'
before=save_inventory(profile);time.sleep(2);assert save_inventory(profile)==before
saves=backup_saves(profile,backup/'totk-saves')
production=Path.home()/'.local/share/ultratears/userdata'
production_before=save_inventory(production)
subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=25)
assert not Path('/proc',str(pid)).exists() and save_inventory(profile)==before
for relative in ['ultratears','bundle.json','build-inputs/build-record.json']:
    p=bundle/relative;dest=backup/'totk-bundle'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    assert not dest.exists();shutil.copy2(p,dest);assert sha(p)==sha(dest)
manifest=json.loads((bundle/'bundle.json').read_text())
record=json.loads((bundle/'build-inputs/build-record.json').read_text())
newsha=sha(candidate/'ultratears')
record['binary_sha256']=newsha
record['live_input_diagnostic_only']=False
record['normal_launch_diagnostics_disabled']=True
record['native_highfps']={'mode':'measured-frame-time','presentation_ceiling':60,
    'verified_opcode_sites':18,'baseline_reemission_matched':True,
    'source_evidence':str(candidate/'prepare.json'),'previous_elf_sha256':sha(bundle/'ultratears')}
changes={'ultratears':(candidate/'ultratears').read_bytes(),
         'build-inputs/build-record.json':(json.dumps(record,indent=2)+'\n').encode()}
for name,data in changes.items():
    manifest['files'][name]['sha256']=hashlib.sha256(data).hexdigest()
    manifest['files'][name]['bytes']=len(data)
changes['bundle.json']=(json.dumps(manifest,indent=2)+'\n').encode()
try:
    for name,data in changes.items():
        p=bundle/name;stage=p.with_name(p.name+'.highfps-new')
        with stage.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        shutil.copymode(p,stage);os.replace(stage,p)
    subprocess.run([sys.executable,str(bundle/'verify_ultratears_bundle.py'),'--root',str(bundle),'--quiet'],check=True)
except Exception:
    for name in changes:
        source=backup/'totk-bundle'/name
        if source.exists():shutil.copy2(source,bundle/name)
    raise
assert sha(bundle/'ultratears')==newsha
assert save_inventory(profile)==before and save_inventory(production)==production_before
result={'at':datetime.now().astimezone().isoformat(),'old_pid':pid,'elf_sha256':newsha,
        'saves_unchanged':True,'production_saves_unchanged':True,'save_backup':saves,
        'rollback':str(backup/'totk-bundle'),'native_build_installed':True,'playability_validated':False}
(report/'totk-install.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
