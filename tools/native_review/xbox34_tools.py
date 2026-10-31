"""Offline, hash-bound derivation of pristine MIT MNG tools; no game assets."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]/'ports/ultratears-linux/xbox'
VENDOR=ROOT/'vendor/macnativegames-f1d00772'
COMMIT='f1d00772df1ac3230268f3124bdeb6b7cc81a61c'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)

def pin():
    info=json.loads((ROOT/'XBOX_STICKS.json').read_text())
    require(info['schema']==1 and info['upstream_commit']==COMMIT and info['glyph_count']==34,'Unexpected Xbox34 pin')
    require(digest(ROOT/'UPSTREAM.json')==info['upstream_pin_sha256'],'Upstream pin changed')
    require(digest(ROOT/'xbox-stick-icons-f1d00772.patch')==info['patch_sha256'],'Xbox34 patch SHA mismatch')
    require(digest(ROOT/'FONTTOOLS.json')==info['fonttools_pin_sha256'],'FontTools pin SHA mismatch')
    require(set(info['after'])=={'make_button_icons.py','test_xbox_sticks.py'},'Unexpected patched file set')
    return info

def fonttools_path():
    pin();base=ROOT/'vendor/fonttools-4.68.0';info=json.loads((ROOT/'FONTTOOLS.json').read_text())
    require(info['version']=='4.68.0','Unexpected FontTools version')
    actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    require(actual==set(info['files']),'Unexpected FontTools file set')
    for name,row in info['files'].items():
        p=base/name
        require(not p.is_symlink() and '..' not in Path(name).parts and not Path(name).is_absolute(),'Unsafe FontTools path')
        require(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'FontTools source SHA mismatch: '+name)
    require(not any(p.is_symlink() for p in [base,*base.rglob('*')]),'FontTools symlink forbidden')
    return base

def apply_patch_exact(source,patch):
    """Strict unified patch: exact old lines/coordinates, no offsets, fuzz or shell."""
    lines=patch.splitlines(keepends=True);i=0;result={}
    while i<len(lines):
        require(lines[i].startswith('--- '),'Invalid patch header');old=lines[i][4:].strip();i+=1
        require(i<len(lines) and lines[i].startswith('+++ '),'Invalid patch target');new=lines[i][4:].strip();i+=1
        require((old,new) in {('a/make_button_icons.py','b/make_button_icons.py'),('/dev/null','b/test_xbox_sticks.py')},'Unexpected patch path')
        name=new[2:];require(name not in result,'Duplicate patch target')
        original=[] if old=='/dev/null' else source[name].splitlines(keepends=True)
        out=[];cursor=0;hunks=0
        while i<len(lines) and not lines[i].startswith('--- '):
            match=re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n?',lines[i])
            require(match is not None,'Invalid hunk');i+=1;hunks+=1
            oldstart=int(match[1]);oldcount=int(match[2] or 1);newstart=int(match[3]);newcount=int(match[4] or 1)
            begin=oldstart-1 if oldcount else oldstart
            require(cursor<=begin<=len(original),'Invalid old hunk position');out.extend(original[cursor:begin]);cursor=begin
            require(len(out)==(newstart-1 if newcount else newstart),'Invalid new hunk position')
            used=added=0
            while i<len(lines) and not lines[i].startswith(('@@ ','--- ')):
                line=lines[i];i+=1;require(line[:1] in (' ','+','-'),'Unsupported patch line')
                if line[0] in (' ','-'):
                    require(cursor<len(original) and original[cursor]==line[1:],'Patch old context mismatch')
                    cursor+=1;used+=1
                if line[0] in (' ','+'):out.append(line[1:]);added+=1
            require((used,added)==(oldcount,newcount),'Hunk line count mismatch')
        require(hunks>0,'Patch target without hunks');out.extend(original[cursor:]);result[name]=''.join(out)
    require(set(result)=={'make_button_icons.py','test_xbox_sticks.py'},'Incomplete patch')
    return result

def derive_tools(pristine,destination,check_tools):
    """Verify original gate first; create and verify a new temporary derived copy."""
    pristine,destination=Path(pristine),Path(destination)
    check_tools(pristine);info=pin()
    require(destination.is_dir() and not any(destination.iterdir()),'Derived destination must be empty')
    original=json.loads((ROOT/'UPSTREAM.json').read_text())
    for name in original['files']:shutil.copyfile(pristine/Path(name).name,destination/Path(name).name)
    content=apply_patch_exact({'make_button_icons.py':(destination/'make_button_icons.py').read_text()},(ROOT/'xbox-stick-icons-f1d00772.patch').read_text())
    for name,text in content.items():(destination/name).write_text(text)
    expected={Path(n).name:row for n,row in original['files'].items()};expected.update(info['after'])
    require({p.name for p in destination.iterdir()}==set(expected),'Derived tool file set mismatch')
    for name,row in expected.items():
        p=destination/name
        require(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'Derived tool SHA mismatch: '+name)
    check_tools(pristine)
    return {'upstream_commit':COMMIT,'patch_sha256':info['patch_sha256'],'after':info['after'],
            'fonttools_pin_sha256':info['fonttools_pin_sha256'],'glyph_count':34}
