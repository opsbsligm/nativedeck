"""Verify a prepared private native bundle. This never certifies gameplay."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

from native_binary_check import inspect
from native_dependencies import dependencies


def safe_relative(name):
    if not isinstance(name, str) or '\\' in name or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('Unsafe bundle path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(ord(c) < 32 for c in name):
        raise ValueError('Unsafe bundle path')
    return path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def verify(root, full=False):
    root = Path(root).resolve()
    manifest = json.loads((root/'bundle.json').read_text())
    if manifest.get('schema') != 1 or manifest.get('kind') != 'ultratears-linux-prepared' or manifest.get('version') != '1.4.3':
        raise ValueError('Unknown native bundle manifest')
    files = manifest.get('files', {})
    resources = {'data/exefs/'+m for m in ('main','subsdk0','sdk')}
    resources |= {'data/romfs/'+n for n in ('romfs.bin','index.json','runtime-index.bin')}
    resources |= {'data/shaders/translated.pack','data/textures/bc7.idx','data/textures/bc7.pack'}
    resources |= {'data/fonts/'+n+'.bfttf' for n in ('0-standard','1-chinese-simplified',
                  '2-chinese-simplified-extension','3-chinese-traditional','4-korean','5-nintendo-extension')}
    if not resources <= files.keys():
        raise ValueError('Incomplete game resource manifest')
    required = {'ultratears', 'run.sh', 'verify_ultratears_bundle.py', 'native_binary_check.py','native_dependencies.py','build-inputs/build-record.json'}
    if not required <= files.keys():
        raise ValueError('Incomplete native bundle manifest')
    for name, info in files.items():
        safe_relative(name)
        path = root/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('缺少资源或路径不安全：'+name)
        if path.stat().st_size != info['bytes']:
            raise ValueError('资源尺寸不一致：'+name)
        critical = name == 'ultratears' or name.startswith(('lib/', 'data/exefs/', 'data/fonts/', 'build-inputs/')) or name.endswith(('.py','.sh'))
        if (full or critical) and digest(path) != info['sha256']:
            raise ValueError('资源校验失败：'+name)
    check = inspect(root/'ultratears', require_ultratears=True)
    if not check['inspection_passed']:
        raise ValueError('游戏程序未通过原生检查：'+','.join(check['errors']))
    for name,path in dependencies(root/'ultratears',[root/'lib']).items():
        if path != (root/'lib'/name).resolve():
            raise ValueError('动态库解析到安装目录之外：'+name)
    return {'native_link_verified': True, 'structural_integrity_verified': True, 'full_hash_verification': full,
            'hardware_validated': False, 'playability_validated': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--full', action='store_true')
    p.add_argument('--quiet', action='store_true')
    args = p.parse_args()
    try:
        result=verify(args.root, args.full)
        if not args.quiet: print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        p.exit(1, str(e)+'\n')
