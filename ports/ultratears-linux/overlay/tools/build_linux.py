"""Build the existing 1.4.3 runtime or real generated game as native Linux x86-64.

runtime creates an archive of the production host/renderer sources, not a game
executable. game requires the real generated tables for all three modules.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

from linux_inputs import verify_generated

ROOT = Path(__file__).resolve().parent.parent


def source_lists():
    # Reuse the upstream source lists without importing its Windows toolchain.
    found = {}
    for node in ast.parse((ROOT/'tools/build_game.py').read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('RUNTIME', 'TARGETS', 'GFX'):
                found[name] = ast.literal_eval(node.value)
    runtime = [p for p in found['RUNTIME'] if not p.endswith('/windows.c')]
    host = [p for p in found['TARGETS']['ultratears'] if p not in ('src/host/profiler.c', 'src/host/watch.c')]
    return runtime + ['src/runtime/platform/linux.c', 'src/runtime/platform/linux_io.c',
                      'src/host/diagnostics_linux.c'] + host + found['GFX']


def pkg_flags(*packages):
    return shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', *packages], text=True))


def ninja_path(path):
    return str(path).replace('$', '$$').replace(' ', '$ ').replace(':', '$:')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', choices=['runtime', 'game'], default='runtime')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--generated', type=Path)
    ap.add_argument('--exefs', type=Path, help='Locally extracted 1.4.3 ExeFS')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--generate-only', action='store_true')
    args = ap.parse_args()
    if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        ap.error('This build entry requires native Linux x86-64')
    if not 1 <= args.jobs <= 4:
        ap.error('--jobs must be between 1 and 4')
    sources = [(ROOT/p).resolve() for p in source_lists()]
    generated = []
    if args.target == 'game':
        if not args.generated or not args.exefs:
            ap.error('game requires --generated and --exefs from checked local 1.4.3 input')
        try:
            generated = verify_generated(args.generated, args.exefs)
        except (OSError, ValueError) as e:
            ap.error(str(e))
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cc = shutil.which('clang')
    cxx = shutil.which('clang++')
    ar = shutil.which('llvm-ar') or shutil.which('ar')
    if not all([cc, cxx, ar, shutil.which('ninja')]):
        ap.error('clang, clang++, ar and ninja are required')
    flags = pkg_flags('sdl3', 'vulkan', 'opus', 'vpx', 'openssl', 'libzstd')
    includes = [f'-I{ROOT/p}' for p in ['src/gfx', 'src/gfx/nvn', 'src/gfx/nvn/include', 'src/gfx/compat', 'src/runtime']]
    if os.environ.get('ULTRS_VULKAN_INCLUDE'):
        includes.insert(0, '-I'+os.environ['ULTRS_VULKAN_INCLUDE'])
    common = ['-D_GNU_SOURCE', '-D_FILE_OFFSET_BITS=64', '-O1', '-gline-tables-only', '-fno-strict-aliasing',
              '-march=x86-64-v3', '-fPIC', '-pthread', *includes, *[x for x in flags if not x.startswith(('-l', '-L', '-Wl,'))]]
    version_text = '#define ULTRS_VERSION "linux-development"\n#define ULTRS_COMMIT "0c9ce8a-native-port"\n'
    version_header = out / 'version.h'
    if not version_header.exists() or version_header.read_text() != version_text:
        version_header.write_text(version_text)
    common.append('-I'+str(out))
    lines = ['builddir = '+ninja_path(out),
             'rule cc', '  command = '+shlex.quote(cc)+' '+shlex.join(common)+' -std=gnu17 -MD -MF $out.d -c $in -o $out',
             '  depfile = $out.d', '  deps = gcc',
             'rule cxx', '  command = '+shlex.quote(cxx)+' '+shlex.join(common)+' -std=c++17 -fno-exceptions -fno-rtti -MD -MF $out.d -c $in -o $out',
             '  depfile = $out.d', '  deps = gcc',
             'rule ar', '  command = '+shlex.quote(ar)+' rcs $out $in',
             'rule link', '  command = '+shlex.quote(cxx)+' -rdynamic -o $out @$out.rsp '+shlex.join(flags+['-pthread', '-ldl', '-lm']),
             '  rspfile = $out.rsp', '  rspfile_content = $in']
    objects = []
    for i, source in enumerate(sources + generated):
        if not source.is_file():
            ap.error('Missing source: '+str(source))
        obj = out/'obj'/(f'{i:04d}_'+source.stem+'.o')
        obj.parent.mkdir(exist_ok=True)
        rule = 'cxx' if source.suffix == '.cpp' else 'cc'
        lines.append(f'build {ninja_path(obj)}: {rule} {ninja_path(source)}')
        objects.append(obj)
    target = out/('libultratears-runtime.a' if args.target == 'runtime' else 'ultratears')
    lines.append(f'build {ninja_path(target)}: {"ar" if args.target == "runtime" else "link"} '+' '.join(ninja_path(o) for o in objects))
    lines.append('default '+ninja_path(target))
    build = out/'build.ninja'
    build.write_text('\n'.join(lines)+'\n')
    print(json.dumps({'target': args.target, 'runtime_sources': len(sources), 'generated_sources': len(generated),
                      'output': str(target), 'game_playability_validated': False}), flush=True)
    if not args.generate_only:
        raise SystemExit(subprocess.call(['ninja', '-f', str(build), '-j', str(args.jobs), '-k', '0']))


if __name__ == '__main__':
    main()
