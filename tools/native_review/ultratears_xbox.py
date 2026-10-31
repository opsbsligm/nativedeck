"""Reuse pinned MacNativeGames icon tools and bake their output into a private RomFS.

Only public scripts are fetched. Game assets are read from local input and never
uploaded. This changes resource bytes at installation, not CPU execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request

from verify_ultratears_bundle import digest, safe_relative

COMMIT = 'f1d00772df1ac3230268f3124bdeb6b7cc81a61c'
PIN = Path(__file__).resolve().parents[2]/'ports/ultratears-linux/xbox/UPSTREAM.json'
FONTS = {'Font/Font'+suffix+'.Nin_NX_NVN.bfarc.zs' for suffix in ('','_CNzh','_TWzh','_KRko')}
LAYOUT = 'UI/LayoutArchive/Common.Product.140.Nin_NX_NVN.blarc.zs'
LIMIT = 256*1024*1024


def regular_inside(root, name):
    safe_relative(name)
    root=Path(root).absolute()
    path=root/name
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing/private UI resource: '+name)
    within=[path,root]
    parent=path.parent
    while parent!=root:
        within.append(parent);parent=parent.parent
    if any(p.is_symlink() for p in within):
        raise ValueError('UI resources must not use symbolic links: '+name)
    return path


def pins():
    pin=json.loads(PIN.read_text())
    if pin.get('commit')!=COMMIT or pin.get('repository')!='https://github.com/ly05010419/MacNativeGames':
        raise ValueError('Unexpected icon tool revision')
    return pin


def check_tools(root):
    pin=pins()
    for name,info in pin['files'].items():
        path=regular_inside(root,Path(name).name)
        if path.stat().st_size!=info['bytes'] or digest(path)!=info['sha256']:
            raise ValueError('Icon tool differs from pinned public source: '+name)
    return pin


def new_destination(destination):
    destination=Path(destination).absolute()
    workspace=(Path.home()/'native-recomp').resolve()
    if not destination.parent.resolve().is_relative_to(workspace) or destination.exists() or destination.is_symlink():
        raise ValueError('Use a new destination inside ~/native-recomp')
    destination.parent.mkdir(parents=True,exist_ok=True)
    return destination


def fetch_tools(destination):
    from ultratears_bundle import publish_no_replace
    destination=new_destination(destination)
    stage=Path(tempfile.mkdtemp(prefix='.xbox-tools-',dir=destination.parent))
    try:
        for name,info in pins()['files'].items():
            if name!='LICENSE' and name not in {
                'games/totk/scripts/'+n for n in ('make_button_icons.py','make_mod_manifest.py','make_romfs_patches.py')}:
                raise ValueError('Unexpected public script path')
            url='https://raw.githubusercontent.com/ly05010419/MacNativeGames/'+COMMIT+'/'+name
            with urllib.request.urlopen(url,timeout=45) as stream:
                body=stream.read(128*1024+1)
            if len(body)!=info['bytes'] or hashlib.sha256(body).hexdigest()!=info['sha256']:
                raise ValueError('Public script download checksum mismatch')
            (stage/Path(name).name).write_bytes(body)
        check_tools(stage)
        publish_no_replace(stage,destination)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'tools':str(destination),'commit':COMMIT,'game_content_downloaded':False}


def manifest(root):
    rows={}
    for line in regular_inside(root,'manifest.tsv').read_text().splitlines():
        if not line or line.startswith('#'):continue
        parts=line.split('\t')
        if len(parts)!=4:raise ValueError('Invalid Xbox resource manifest')
        name,length,replacement,original=parts
        safe_relative(name)
        if name in rows or not length.isascii() or not length.isdecimal():raise ValueError('Invalid/duplicate UI record')
        size=int(length)
        if not 0<size<=LIMIT or not all(re.fullmatch('[0-9a-f]{64}',h) for h in (replacement,original)):
            raise ValueError('Invalid UI size or original digest')
        if (name not in FONTS and name!=LAYOUT and not re.fullmatch(
                r'System/Resource/ResourceSizeTable\.Product\.[0-9]+\.Nin_NX_NVN\.rsizetable\.zs',name)):
            raise ValueError('Unexpected non-UI resource: '+name)
        path=regular_inside(root,name)
        if path.stat().st_size!=size or digest(path)!=replacement:raise ValueError('Changed Xbox resource: '+name)
        rows[name]={'bytes':size,'sha256':replacement,'original_sha256':original}
    if not (FONTS|{LAYOUT})<=rows.keys() or len(rows)!=6 or sum(r['bytes'] for r in rows.values())>2*LIMIT:
        raise ValueError('Xbox font, HUD and resource-size coverage is incomplete')
    return rows


def prepare(romfs, tools, destination, python):
    from ultratears_bundle import GAME, publish_no_replace
    romfs,tools=Path(romfs).resolve(),Path(tools).resolve()
    check_tools(tools)
    from xbox34_tools import derive_tools, fonttools_path
    destination=new_destination(destination)
    source=[regular_inside(romfs,n) for n in ('index.json','runtime-index.bin','romfs.bin')]
    before=[p.stat() for p in source]
    index=json.loads(source[0].read_text())
    if index.get('status')!='pass' or index.get('content_sha256')!=GAME['romfs_content'] or len(index.get('files',[]))!=GAME['romfs_files']:
        raise ValueError('Icon preparation requires the checked 1.4.3 RomFS inventory')
    env=dict(os.environ)
    for key in ('PYTHONOPTIMIZE','PYTHONPATH','PYTHONHOME'):env.pop(key,None)
    env['PYTHONNOUSERSITE']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']=str(fonttools_path())
    subprocess.run([str(python),'-S','-c','from compression import zstd; import fontTools'],env=env,check=True)
    stage=Path(tempfile.mkdtemp(prefix='.xbox-prompts-',dir=destination.parent))
    effective=Path(tempfile.mkdtemp(prefix='.xbox34-tools-',dir=destination.parent))
    try:
        derivation=derive_tools(tools,effective,check_tools)
        subprocess.run([str(python),'-S',str(effective/'make_button_icons.py'),str(stage),
                        '--romfs',str(romfs),'--version','v143','--style','xbox'],env=env,check=True)
        rows=manifest(stage)
        if any((a.st_size,a.st_mtime_ns,a.st_ino)!=(b.st_size,b.st_mtime_ns,b.st_ino)
               for a,b in zip(before,[p.stat() for p in source])):
            raise ValueError('RomFS input changed during icon preparation')
        record={'schema':1,'kind':'ultratears-xbox-ui','version':'1.4.3','tool_commit':COMMIT,
                'input_mapping':'position','resources':rows,
                'coverage':['four regional icon fonts','eight gameplay HUD textures','resource-size table'],
                'tutorial_images_complete':False,'hardware_validated':False,'tool_derivation':derivation}
        (stage/'xbox-ui.json').write_text(json.dumps(record,indent=2)+'\n')
        publish_no_replace(stage,destination)
    finally:
        if effective.exists():shutil.rmtree(effective)
        if stage.exists():shutil.rmtree(stage)
    return {'prepared':str(destination),'hardware_validated':False,'all_xbox_prompts_validated':False}


def apply_to_stage(romfs, mod):
    """Append replacements only to the installer's private staging image.

    Validate every original and replacement before changing bytes. Any later
    failure is handled by discarding the entire unpublished installation stage.
    The immutable original source image is never passed to this function.
    """
    romfs,mod=Path(romfs),Path(mod)
    rows=manifest(mod)
    record=json.loads(regular_inside(mod,'xbox-ui.json').read_text())
    if any(record.get(k)!=v for k,v in {'schema':1,'kind':'ultratears-xbox-ui','version':'1.4.3',
            'tool_commit':COMMIT,'input_mapping':'position','resources':rows}.items()):
        raise ValueError('Xbox UI build record mismatch')
    doc=json.loads((romfs/'index.json').read_text())
    files=doc['files'];by_name={row['path']:row for row in files}
    native=bytearray((romfs/'runtime-index.bin').read_bytes())
    if len(native)<24 or native[:8]!=b'TOTKRFS1' or struct.unpack_from('<Q',native,8)[0]!=len(files):
        raise ValueError('Invalid staged native RomFS index')
    with (romfs/'romfs.bin').open('rb') as image:
        for name,info in rows.items():
            if name not in by_name:raise ValueError('UI resource absent from this game version: '+name)
            old=by_name[name];image.seek(old['offset']);remaining=old['size'];h=hashlib.sha256()
            while remaining:
                block=image.read(min(1024*1024,remaining))
                if not block:raise ValueError('Short original UI resource')
                h.update(block);remaining-=len(block)
            if h.hexdigest()!=info['original_sha256']:raise ValueError('UI resource is from another base: '+name)
    base_content=doc.pop('content_sha256')
    with (romfs/'romfs.bin').open('ab') as image:
        for i,row in enumerate(files):
            name=row['path']
            if name not in rows:continue
            info=rows[name];image.write(b'\0'*(-image.tell()%16));at=image.tell()
            with regular_inside(mod,name).open('rb') as replacement:
                shutil.copyfileobj(replacement,image,1024*1024)
            row.update(offset=at,size=info['bytes'])
            struct.pack_into('<QQ',native,24+i*24,at,info['bytes'])
        image.flush();os.fsync(image.fileno())
    # Keep base identity distinct: a modified image is never declared canonical.
    doc.update(status='ui-patched',base_content_sha256=base_content,ui_resources=rows)
    (romfs/'index.json').write_text(json.dumps(doc,separators=(',',':'))+'\n')
    (romfs/'runtime-index.bin').write_bytes(native)
    # Check the bytes just appended, including replacement files changed mid-copy.
    with (romfs/'romfs.bin').open('rb') as image:
        for name,info in rows.items():
            image.seek(by_name[name]['offset'])
            if hashlib.sha256(image.read(info['bytes'])).hexdigest()!=info['sha256']:
                raise ValueError('Xbox UI copy failed verification: '+name)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    fetch=sub.add_parser('fetch-tools');fetch.add_argument('--destination',type=Path,required=True)
    build=sub.add_parser('prepare')
    for name in ('romfs','destination'):build.add_argument('--'+name,type=Path,required=True)
    build.add_argument('--tools',type=Path,default=PIN.parent/'vendor/macnativegames-f1d00772',help='Pristine pinned tools; defaults to offline vendor')
    build.add_argument('--python',type=Path,default=Path(sys.executable))
    args=p.parse_args()
    try:
        result=fetch_tools(args.destination) if args.action=='fetch-tools' else prepare(args.romfs,args.tools,args.destination,args.python)
        print(json.dumps(result,ensure_ascii=False))
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as e:p.exit(1,str(e)+'\n')
