"""Resolve native Linux dependencies without launching game code."""
import os
from pathlib import Path
import re
import subprocess
from native_binary_check import inspect

SYSTEM_LIBS = {'libc.so.6','libm.so.6','libdl.so.2','libpthread.so.0','librt.so.1',
               'libresolv.so.2','libutil.so.1','libgcc_s.so.1','libstdc++.so.6',
               'ld-linux-x86-64.so.2','libvulkan.so.1'}
DRIVER_PREFIXES = ('libGL','libEGL','libdrm','libvulkan_','libVkLayer')

def forbidden(path):
    words=('wine','proton','dxvk','vkd3d','box64','qemu','fex','compattools','steamlinuxruntime','pressure-vessel')
    return any(any(p.lower().lstrip('.').startswith(w) or p.lower().startswith('lib'+w) for w in words) for p in Path(path).parts)


def dependencies(binary, search):
    interpreter=inspect(binary).get('interpreter')
    env=dict(os.environ);env.pop('LD_PRELOAD',None)
    env['LD_LIBRARY_PATH']=os.pathsep.join(str(Path(p).resolve()) for p in search)
    r=subprocess.run(['ldd','-r',str(binary)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
    if 'not found' in r.stdout or 'undefined symbol:' in r.stdout: raise ValueError('Unresolved native dependencies:\n'+r.stdout)
    result={}
    for line in r.stdout.splitlines():
        if '=>' not in line: continue
        m=re.fullmatch(r'\s*(\S+)\s+=>\s+(/.*?)\s+\(0x[0-9a-fA-F]+\)\s*',line)
        if not m: raise ValueError('Unrecognized dependency: '+line)
        name,path=m.groups()
        # SteamOS/glibc can echo PT_INTERP as an absolute "name => path";
        # Ubuntu's ldd commonly prints it without =>. Only the exact native
        # system interpreter gets this exception, never arbitrary DT_NEEDED.
        if name==interpreter and name.startswith('/'):
            loader=Path(path).resolve()
            system=any(loader.is_relative_to(base) for base in
                       (Path('/lib'),Path('/lib64'),Path('/usr/lib'),Path('/usr/lib64')))
            if (Path(name).name!='ld-linux-x86-64.so.2' or loader.name!='ld-linux-x86-64.so.2'
                    or not system or forbidden(name) or forbidden(path)
                    or not inspect(loader)['inspection_passed']):
                raise ValueError('Invalid native system interpreter: '+name)
            name=Path(name).name
        if '/' in name or forbidden(path) or forbidden(name): raise ValueError('Non-native/unsafe dependency: '+name)
        if name in SYSTEM_LIBS or name.startswith(DRIVER_PREFIXES): continue
        path=Path(path).resolve()
        if not inspect(path)['inspection_passed']: raise ValueError('Invalid dependency ELF: '+name)
        result[name]=path
    return result


