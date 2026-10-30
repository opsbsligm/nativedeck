"""Prepare a private native UltraTears 1.4.3 directory; never publish game data.

Identity constants and formats: kuraeow/ultratears commit
0c9ce8afd4c3ab81c33200917af51fb9807aeef0, GPL-3.0-or-later.
The supplied shader inventory is checked for completeness against its pack;
actual gameplay, Chinese display and Xbox prompts require hardware acceptance.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile

from native_binary_check import inspect
from native_dependencies import dependencies, forbidden
from verify_ultratears_bundle import digest, safe_relative, verify

GAME = {
    'exefs': {'main':'e84a90d551fed0824b4b74933b9c6d043c458521363a7cea58b2faca1822dc9e',
              'subsdk0':'767c35bcd7d23e78f9063c69b638290b8b83f91e839beb10799e6576960179b1',
              'sdk':'1d187f29784cd0af46e9e123fc2a62c77b3b07c5a39c8633d90d6c80de64e4ad'},
    'romfs_files':304243, 'romfs_bytes':17026725026,
    'romfs_content':'b2a2e966a06158e098c03e564f77fd72809bc57275f04eb0725bcde14d522056',
}
FONTS = ('0-standard','1-chinese-simplified','2-chinese-simplified-extension',
         '3-chinese-traditional','4-korean','5-nintendo-extension')
RUN = '''#!/usr/bin/env bash
set -euo pipefail
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
case "${1-}" in
  --verify) exec python3 "$here/verify_ultratears_bundle.py" --root "$here" --full ;;
esac
python3 "$here/verify_ultratears_bundle.py" --root "$here" --quiet
preload="${LD_PRELOAD-}"
case "${preload,,}" in
  *wine*|*proton*|*dxvk*|*vkd3d*|*box64*|*qemu*|*libfex*) printf '%s\n' '启动环境加载了不支持的兼容组件。' >&2; exit 1 ;;
esac
app_data="${XDG_DATA_HOME:-$HOME/.local/share}/ultratears"
mkdir -p -m 700 "$app_data/userdata" "$app_data/cache"
exec 9>"$app_data/session.lock"
if ! flock -n 9; then
  printf '%s\n' '《王国之泪》已经运行，请先退出现有游戏。' >&2
  exit 75
fi
export LARECOMP_DATA_ROOT="$app_data"
export TOTK_PROFILE_DIR="$app_data/userdata"
export TOTK_SHADER_BIN="$app_data/cache/compiled.bin"
export TOTK_ROMFS="$here/data/romfs"
export TOTK_SHADER_PACK="$here/data/shaders/translated.pack"
export TOTK_BC7_DIR="$here/data/textures"
export TOTK_SHARED_FONTS="$here/data/fonts"
export TOTK_LANG="${TOTK_LANG:-zh-Hans}"
export TOTK_OPERATION_MODE="${TOTK_OPERATION_MODE:-handheld}"
export TOTK_VK_POOL_SHADOW="${TOTK_VK_POOL_SHADOW:-0}"
export LD_LIBRARY_PATH="$here/lib"
cd -- "$here"
exec "$here/ultratears" "$here/data/exefs" "$@"
'''


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Required regular resource missing: '+str(path))
    return path


def romfs_check(root):
    image = regular(root/'romfs.bin')
    index = regular(root/'index.json')
    native = regular(root/'runtime-index.bin')
    if index.stat().st_size > 128*1024*1024:
        raise ValueError('RomFS JSON exceeds size bound')
    doc = json.loads(index.read_text())
    rows = doc.get('files', [])
    if doc.get('status') != 'pass' or len(rows) != GAME['romfs_files'] or doc.get('content_sha256') != GAME['romfs_content']:
        raise ValueError('RomFS does not match 1.4.3 inventory')
    image_size=image.stat().st_size
    if image_size < GAME['romfs_bytes']:
        raise ValueError('RomFS image is incomplete')
    whole, content = hashlib.sha256(), hashlib.sha256()
    previous, offset, text_at, announced = None, 0, 0, 0
    with native.open('rb') as n, mmap.mmap(n.fileno(),0,access=mmap.ACCESS_READ) as mm, image.open('rb') as f:
        if len(mm)<24 or mm[:8]!=b'TOTKRFS1': raise ValueError('Bad runtime RomFS index')
        count, strings = struct.unpack_from('<QQ',mm,8)
        if count!=len(rows) or strings!=24+count*24 or strings>len(mm): raise ValueError('Bad runtime index layout')
        for i,row in enumerate(rows):
            name = row['path']; safe_relative(name)
            if previous is not None and name<=previous: raise ValueError('RomFS paths are not unique/sorted')
            previous=name
            length, at = row['size'], row['offset']
            if type(length) is not int or length<0 or type(at) is not int or at != (offset+15)//16*16:
                raise ValueError('Invalid RomFS file extent')
            if at+length>image_size: raise ValueError('RomFS extent exceeds image')
            raw=name.encode()+b'\0'
            record=struct.unpack_from('<QQII',mm,24+i*24)
            if record!=(at,length,text_at,len(raw)) or mm[strings+text_at:strings+text_at+len(raw)]!=raw:
                raise ValueError('Runtime RomFS index differs from JSON')
            text_at+=len(raw)
            padding=f.read(at-offset)
            if len(padding)!=at-offset or any(padding): raise ValueError('Invalid RomFS alignment padding')
            whole.update(padding); part=hashlib.sha256(); remaining=length
            while remaining:
                block=f.read(min(1024*1024,remaining))
                if not block: raise ValueError('Short RomFS read')
                part.update(block); whole.update(block); remaining-=len(block)
            content.update(part.digest());offset=at+length
            if offset-announced>=1024**3:
                print(f'Verified RomFS {offset/1024**3:.1f}GiB',flush=True);announced=offset
        if offset!=image_size or strings+text_at!=len(mm): raise ValueError('Unexpected trailing RomFS bytes')
    if content.hexdigest()!=GAME['romfs_content']: raise ValueError('RomFS bytes differ from 1.4.3 content hash')
    return whole.hexdigest()


def shader_check(pack, jobs):
    keys=set()
    with regular(jobs).open() as stream:
        for line in stream:
            key=json.loads(line)['job']['key']
            if not re.fullmatch('[0-9a-f]{64}',key) or key in keys: raise ValueError('Invalid/duplicate shader inventory key')
            keys.add(key)
    if not keys: raise ValueError('Empty shader inventory')
    with regular(pack).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
        if len(mm)<32 or mm[:8]!=b'UTSPACK1': raise ValueError('Invalid shader pack')
        version,count,at,reserved=struct.unpack_from('<IIQQ',mm,8)
        if version!=1 or reserved or count!=len(keys) or at<32 or at+count*64!=len(mm): raise ValueError('Incomplete shader index')
        seen=[];cursor=32
        for i in range(count):
            key,jo,so,jn,sn,stamp,zero=struct.unpack_from('<32sQQIIII',mm,at+i*64)
            if zero or jo!=cursor or not 0<jn<=1024*1024 or so!=jo+jn or sn<20 or sn%4 or so+sn>at:
                raise ValueError('Invalid shader extent')
            j,s=mm[jo:so],mm[so:so+sn]
            if not isinstance(json.loads(j),dict): raise ValueError('Invalid shader metadata')
            magic,version,_,bound,schema=struct.unpack_from('<5I',s)
            if magic!=0x07230203 or not 0x10000<=version<=0x10600 or not bound or schema:
                raise ValueError('Invalid SPIR-V header')
            actual=struct.unpack('<I',hashlib.sha256(j+s).digest()[:4])[0]|1
            if stamp!=actual: raise ValueError('Shader translation stamp mismatch')
            seen.append(key.hex());cursor=so+sn
        if cursor!=at or seen!=sorted(keys): raise ValueError('Shader pack and supplied inventory differ')


def font_check(path):
    regular(path)
    n=path.stat().st_size
    if not 8<n<64*1024*1024: raise ValueError('Invalid shared font size')
    with path.open('rb') as f: a,b=struct.unpack('>II',f.read(8))
    if b^(a^0x18029a7f)!=n-8: raise ValueError('Invalid BFTTF font header: '+path.name)


def texture_check(index, pack):
    size=regular(pack).stat().st_size
    n=regular(index).stat().st_size
    if not size or not n or n%32: raise ValueError('Missing or truncated BC7 cache')
    with index.open('rb') as f:
        while record:=f.read(32):
            a,b,off,length,fmt=struct.unpack('<QQQII',record)
            if not (a or b) or not length or off+length>size or fmt not in (0,1):
                raise ValueError('Invalid BC7 cache extent')


def publish_no_replace(source,destination):
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None: raise OSError('Linux renameat2 is required for no-overwrite publication')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1):
        number=ctypes.get_errno();raise OSError(number,os.strerror(number),str(destination))


def prepare(binary,exefs,data,jobs,destination,library_dirs=(),workspace=None,build_record=None,xbox_ui=None):
    binary,exefs,data,jobs=map(lambda p:Path(p).resolve(),(binary,exefs,data,jobs))
    workspace=(Path.home()/'native-recomp' if workspace is None else Path(workspace)).resolve()
    destination=Path(destination).absolute()
    if not destination.parent.resolve().is_relative_to(workspace) or destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be new and inside the project workspace')
    if destination.resolve().is_relative_to(data) or data.is_relative_to(destination.resolve()):
        raise ValueError('Bundle must be separate from source data')
    elf=inspect(regular(binary),require_ultratears=True)
    if not elf['inspection_passed']: raise ValueError('Not a complete native UltraTears executable: '+','.join(elf['errors']))
    record_path=regular(binary.with_suffix('.build.json') if build_record is None else Path(build_record))
    record=json.loads(record_path.read_text())
    counts={m:elf['function_counters'].get(m+'_fn_count') for m in ('main','subsdk0','sdk')}
    if (record.get('schema')!=1 or record.get('kind')!='ultratears-linux-build' or record.get('version')!='1.4.3'
            or record.get('upstream')!='0c9ce8afd4c3ab81c33200917af51fb9807aeef0'
            or record.get('exefs')!=GAME['exefs'] or record.get('binary_sha256')!=digest(binary)
            or record.get('function_counts')!=counts
            or not re.fullmatch('[0-9a-f]{64}',record.get('generated_manifest_sha256',''))):
        raise ValueError('Executable does not match the checked game build record')
    files={'ultratears':binary,'build-inputs/build-record.json':record_path}; hashes={}
    for module,want in GAME['exefs'].items():
        path=regular(exefs/module)
        if digest(path)!=want: raise ValueError('Not TOTK 1.4.3 ExeFS: '+module)
        files['data/exefs/'+module]=path;hashes['data/exefs/'+module]=want
    if (exefs/'main.npdm').is_file(): files['data/exefs/main.npdm']=regular(exefs/'main.npdm')
    hashes['data/romfs/romfs.bin']=romfs_check(data/'romfs')
    shader_check(data/'shaders/translated.pack',jobs)
    texture_check(data/'textures/bc7.idx',data/'textures/bc7.pack')
    for font in FONTS:
        path=data/'fonts'/(font+'.bfttf');font_check(path);files['data/fonts/'+path.name]=path
    for name in ('romfs/romfs.bin','romfs/index.json','romfs/runtime-index.bin','shaders/translated.pack','textures/bc7.idx','textures/bc7.pack'):
        files['data/'+name]=regular(data/name)
    for name,path in dependencies(binary,library_dirs).items():files['lib/'+name]=path
    here=Path(__file__).resolve().parent
    for name in ('verify_ultratears_bundle.py','native_binary_check.py','native_dependencies.py'):files[name]=here/name
    files['build-inputs/shader-jobs.jsonl']=regular(jobs)
    peak=sum(p.stat().st_size for p in files.values())
    ui_rows=None
    if xbox_ui is not None:
        from ultratears_xbox import manifest as ui_manifest
        xbox_ui=Path(xbox_ui).resolve();ui_rows=ui_manifest(xbox_ui)
        files['build-inputs/xbox-ui.json']=regular(xbox_ui/'xbox-ui.json')
        files['build-inputs/xbox-manifest.tsv']=regular(xbox_ui/'manifest.tsv')
        peak+=sum(r['bytes']+16 for r in ui_rows.values())
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free < peak+4*1024**3: raise ValueError('Insufficient space for bundle plus 4GiB reserve')
    print(f'Additional disk estimate {peak/1024**3:.2f}GiB; source resources retained',flush=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+destination.name+'.partial-',dir=destination.parent))
    try:
        (stage/'lib').mkdir()
        manifest={}
        for name,source in files.items():
            safe_relative(name)
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
            before=source.stat();expected=hashes.get(name) or digest(source)
            shutil.copyfile(source,target)
            after=source.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or digest(target)!=expected:
                raise ValueError('Resource changed or copy verification failed: '+name)
            target.chmod(0o755 if name=='ultratears' else 0o644)
            with target.open('rb') as stored:os.fsync(stored.fileno())
            manifest[name]={'bytes':target.stat().st_size,'sha256':expected}
            print('Copied and verified '+name,flush=True)
        ui_record=None
        if ui_rows is not None:
            from ultratears_xbox import apply_to_stage
            ui_record=apply_to_stage(stage/'data/romfs',xbox_ui)
            for name in ('romfs.bin','index.json','runtime-index.bin'):
                relative='data/romfs/'+name;path=stage/relative
                manifest[relative]={'bytes':path.stat().st_size,'sha256':digest(path)}
                with path.open('rb') as stored:os.fsync(stored.fileno())
        script=stage/'run.sh';script.write_text(RUN);script.chmod(0o755)
        manifest['run.sh']={'bytes':script.stat().st_size,'sha256':digest(script)}
        doc={'schema':1,'kind':'ultratears-linux-prepared','version':'1.4.3','files':manifest,
             'hardware_validated':False,'chinese_display_validated':False,'xbox_prompts_validated':False,
             'shader_scope':'pack matches supplied shader inventory; actual GPU translation unvalidated'}
        if ui_record is not None:doc['xbox_ui']=ui_record
        (stage/'bundle.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
        verify(stage,full=True)
        # Persist the staged tree before its single no-overwrite publication.
        for file in (stage/'run.sh',stage/'bundle.json'):
            with file.open('rb') as stored:os.fsync(stored.fileno())
        directories=sorted([stage,*[p for p in stage.rglob('*') if p.is_dir()]],key=lambda p:len(p.parts),reverse=True)
        for directory in directories:
            fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        publish_no_replace(stage,destination)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'bundle':str(destination),'prepared':True,'hardware_validated':False,'playability_validated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','exefs','data','shader-jobs','destination'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--build-record',type=Path)
    p.add_argument('--xbox-ui',type=Path,help='Locally generated pinned Xbox resources; baked into the staged RomFS')
    p.add_argument('--library-dir',type=Path,action='append',default=[])
    a=p.parse_args()
    if sys.platform!='linux' or platform.machine().lower() not in ('x86_64','amd64'):p.error('Native Linux x86-64 is required')
    try:
        print(json.dumps(prepare(a.binary,a.exefs,a.data,a.shader_jobs,a.destination,a.library_dir,build_record=a.build_record,xbox_ui=a.xbox_ui),ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError,struct.error) as e:
        p.exit(1,str(e)+'\n')
