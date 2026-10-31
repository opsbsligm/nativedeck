# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic cache cases; no external services or game input."""
import fcntl
import hashlib
import os
import struct
import subprocess
from pathlib import Path


def run_suite(exe, root):
    results = []
    env = dict(os.environ, TMPDIR=str(root))
    def rec(a=1,b=9,off=0,n=16,fmt=0):return struct.pack('<QQQII',a,b,off,n,fmt)
    def fixture(name):
        d=root/name;d.mkdir();base=d/'base';base.mkdir();cache=d/'cache';cache.mkdir()
        (base/'bc7.pack').write_bytes(b'\x11'*16);(base/'bc7.idx').write_bytes(rec())
        for f in base.iterdir():f.chmod(0o444)
        base.chmod(0o555)
        return base,cache
    def snap(d):return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in d.iterdir() if f.is_file()}
    def run(mode,base,cache,extra=None):
        e=dict(env,TOTK_BC7_DIR=str(base));e.pop('TOTK_BC7_CACHE_DIR',None)
        if cache is not None:e['TOTK_BC7_CACHE_DIR']=str(cache)
        e.update(extra or {})
        subprocess.run([str(exe),mode],env=e,check=True,timeout=25)
    def add(name):results.append(name);print('PASS '+name,flush=True)
    for mode in ['normal','queue','concurrent']:
        base,cache=fixture(mode);before=snap(base)
        run(mode,base,cache);assert snap(base)==before
        run('concurrent-reload' if mode=='concurrent' else 'reload',base,cache)
        assert snap(base)==before
        raw=(cache/'bc7.idx').read_bytes();assert len(raw)%32==0
        for i in range(0,len(raw),32):assert struct.unpack('<QQQII',raw[i:i+32])[2]<(1<<63)
        add(mode+' + second-process reload + readonly base SHA256 + disk ABI')
    base,cache=fixture('fallback');before=snap(base)
    run('normal',base,cache,{'HARNESS_NO_MMAP':'1'});run('reload',base,cache,{'HARNESS_NO_MMAP':'1'});assert snap(base)==before
    add('mmap failure uses correct base/delta streams')
    base,cache=fixture('duplicate')
    (cache/'bc7.pack').write_bytes(b'\x33'*8+b'\x44'*8)
    (cache/'bc7.idx').write_bytes(rec(off=0,n=8,fmt=1)+rec(off=8,n=8,fmt=1))
    before=snap(base);delta=snap(cache);run('duplicate',base,cache);assert snap(base)==before and snap(cache)==delta
    add('latest delta duplicate beats base + runtime store preserves existing key')
    bads={'truncated':rec()+b'x','wrapped':rec(off=(1<<64)-8),'tag-bit':rec(off=1<<63),'oob':rec(off=15,n=16),'zero-key':rec(a=0,b=0),'zero-len':rec(n=0),'bad-format':rec(fmt=99)}
    for side in ['base','delta']:
        for name,bad in bads.items():
            base,cache=fixture(side+'-'+name)
            target=base if side=='base' else cache
            (target/'bc7.idx').chmod(0o644) if (target/'bc7.idx').exists() else None
            (target/'bc7.idx').write_bytes(bad)
            if side=='delta':(cache/'bc7.pack').write_bytes(b'\x22'*16)
            before=snap(base);delta=snap(cache);run('fail',base,cache)
            assert snap(base)==before and snap(cache)==delta
            add(side+' '+name+' fails closed without append')
    for name in ['same-dir','symlink-dir','hardlink-pack','hardlink-idx','cross-hardlink','symlink-pack','same-delta-files']:
        base,cache=fixture(name)
        if name=='same-dir':cache=base
        elif name=='symlink-dir':cache.rmdir();cache.symlink_to(base,target_is_directory=True)
        elif name=='hardlink-pack':os.link(base/'bc7.pack',cache/'bc7.pack')
        elif name=='hardlink-idx':os.link(base/'bc7.idx',cache/'bc7.idx')
        elif name=='cross-hardlink':os.link(base/'bc7.idx',cache/'bc7.pack')
        elif name=='symlink-pack':(cache/'bc7.pack').symlink_to(base/'bc7.pack')
        else:(cache/'bc7.pack').write_bytes(b'');os.link(cache/'bc7.pack',cache/'bc7.idx')
        before=snap(base);run('fail',base,cache);assert snap(base)==before;add('alias rejected '+name)
    base,cache=fixture('legacy');base.chmod(0o755)
    for f in base.iterdir():f.chmod(0o644)
    run('normal',base,None);run('reload',base,None)
    assert (base/'bc7.pack').stat().st_size==32 and (base/'bc7.idx').stat().st_size==64
    add('legacy unset overlay appends/reloads in original directory')
    base,cache=fixture('empty-env');base.chmod(0o755)
    for f in base.iterdir():f.chmod(0o644)
    run('normal',base,None,{'TOTK_BC7_CACHE_DIR':''});run('reload',base,None)
    add('empty overlay environment retains legacy mode')
    base,cache=fixture('missing-base');base.chmod(0o755);(base/'bc7.idx').unlink();base.chmod(0o555);before=snap(base)
    run('fail',base,cache);assert snap(base)==before;add('missing base fails closed')
    base,cache=fixture('long-path');before=snap(base)
    run('fail',base,'x'*600);assert snap(base)==before;add('overlong cache path fails closed')
    for mode in ['io-pack','io-idx']:
        base,cache=fixture(mode)
        if mode=='io-idx':
            (cache/'bc7.pack').write_bytes(b'\x55'*16)
            (cache/'bc7.idx').write_bytes(rec(a=88,n=16))
        before=snap(base);run(mode,base,cache);assert snap(base)==before
        run('only-base',base,cache);add(mode+' short write disables cache + validated restart')
    for file in ['bc7.pack','bc7.idx']:
        base,cache=fixture('locked-'+file)
        for name in ['bc7.pack','bc7.idx']:(cache/name).write_bytes(b'')
        before=snap(base);delta=snap(cache)
        with (cache/file).open('rb') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            run('fail',base,cache)
        assert snap(base)==before and snap(cache)==delta
        run('normal',base,cache);add('cross-process exclusive lock '+file+' + retry after release')
    return results
