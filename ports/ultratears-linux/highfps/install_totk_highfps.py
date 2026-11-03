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
from build_codegen_candidate import verify_receipt

def require(condition, message='High-fps validation failed'):
    if not condition:
        raise ValueError(message)

root=Path.home()/'native-recomp'
bundle=root/'ultratears/releases/v143-20261031-first'
report=root/'evidence/library-unlock-20261103'
backup=report/'backup'
candidate=root/'work/totk-1.4.3-20261031/highfps-20261103'
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
require((candidate/'prepare.json').is_file() and (candidate/'ultratears').stat().st_size>500*1024**2, 'High-fps validation failed')
require(shutil.disk_usage(root).free>2*1024**3, 'High-fps validation failed')
sys.path.insert(0,str(root/'swr'))
from botw_launch import save_inventory,backup_saves
build_receipt=verify_receipt(candidate)
unit='nd-totk-v143-first-boot-20261031'
pid=int(subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','--value'],text=True))
require(pid>0 and Path('/proc',str(pid),'exe').resolve()==bundle/'ultratears', 'High-fps validation failed')
env=dict(x.decode().split('=',1) for x in Path('/proc',str(pid),'environ').read_bytes().split(b'\0') if b'=' in x)
profile=Path(env['XDG_DATA_HOME'])/'ultratears/userdata'
require(profile==Path.home()/'.local/share/ultratears/test-profiles/v8-opening-20261102/ultratears/userdata', 'High-fps validation failed')
before=save_inventory(profile);time.sleep(2);require(save_inventory(profile)==before, 'High-fps validation failed')
saves=backup_saves(profile,backup/'totk-saves')
production=Path.home()/'.local/share/ultratears/userdata'
production_before=save_inventory(production)
subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=25)
require(not Path('/proc',str(pid)).exists() and save_inventory(profile)==before, 'High-fps validation failed')
for relative in ['ultratears','bundle.json','build-inputs/build-record.json']:
    p=bundle/relative;dest=backup/'totk-bundle'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    require(not dest.exists(), 'High-fps validation failed');shutil.copy2(p,dest);require(sha(p)==sha(dest), 'High-fps validation failed')
manifest=json.loads((bundle/'bundle.json').read_text())
record=json.loads((bundle/'build-inputs/build-record.json').read_text())
newsha=sha(candidate/'ultratears')
selection=json.loads((candidate/'codegen-selection.json').read_text())
require(selection['numeric_chunks']==1432, 'Incomplete V8 codegen selection')
for path,expected in selection['immutable_object_hashes'].items():
    require(sha(Path(path))==expected, 'Immutable V8/host input changed: '+path)
for item in selection['patched_sources']:
    require(sha(Path(item['candidate']))==item['candidate_sha256'], 'Patched input changed')
record['compile_overrides_sha256']=selection['compile_overrides_sha256']
record['compile_overrides_files']=selection['compile_overrides_files']
record['native_codegen_recovery']={'selection_sha256':sha(candidate/'codegen-selection.json'),
    'build_receipt_sha256':sha(candidate/'build-receipt.json'),
    'numeric_chunks':selection['numeric_chunks'],'baseline_elf_sha256':selection['baseline_elf_sha256']}
record['binary_sha256']=newsha
record['live_input_diagnostic_only']=False
record['normal_launch_diagnostics_disabled']=True
record['native_highfps']={'mode':'measured-frame-time','presentation_ceiling':60,
    'verified_opcode_sites':18,'baseline_reemission_matched':True,
    'source_evidence':str(candidate/'prepare.json'),'previous_elf_sha256':sha(bundle/'ultratears')}
record['native_highfps']['input_sha256']={name:sha(candidate/name)
    for name in ['prepare.json','build.ninja','nd_totk_timing.c','nd_totk_timing.h','hle_nvn.c']}
record['native_highfps']['generated_chunks']=json.loads((candidate/'prepare.json').read_text())['chunks']
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
require(sha(bundle/'ultratears')==newsha, 'High-fps validation failed')
require(save_inventory(profile)==before and save_inventory(production)==production_before, 'High-fps validation failed')
result={'at':datetime.now().astimezone().isoformat(),'old_pid':pid,'elf_sha256':newsha,
        'saves_unchanged':True,'production_saves_unchanged':True,'save_backup':saves,
        'rollback':str(backup/'totk-bundle'),'native_build_installed':True,'playability_validated':False}
(report/'totk-install.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
