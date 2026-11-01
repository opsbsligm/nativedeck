#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Rebuild the SHA-bound candidate with git apply, then run native Linux tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

# Never create __pycache__ in a copied repository or read-only source checkout.
sys.dont_write_bytecode = True
from production_binding import rebuild_production
from test_cache import run_suite
from test_integrity import run_integrity_checks

PROJECT_INCLUDES = (
    '#include "../runtime/platform/linux_io.h"',
    '#include "compat/gfx_compat.h"',
    '#include "host/hle.h"',
    '#include "vkb.h"',
    '#include "tex/bc7.h"',
    '#include "tex/bc7key.h"',
)


def require_sha(data, expected, label):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise RuntimeError("{} SHA256 mismatch: expected {}, got {}".format(label, expected, actual))


def rebuild(package, work, manifest):
    source = package / manifest['fixture']
    patch = package / manifest['patch']
    require_sha(source.read_bytes(), manifest['source_sha256'], 'upstream fixture')
    require_sha(patch.read_bytes(), manifest['patch_sha256'], 'Linux patch')
    target = work / 'src/gfx/vkb_bc7.c'
    target.parent.mkdir(parents=True)
    shutil.copyfile(str(source), str(target))
    # An isolated repository makes execution independent of the caller's cwd/git state.
    # Ignore ambient git redirection and custom templates; no checkout/commit/remote exists.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    for command in (
        ['git', '-c', 'core.attributesFile=' + os.devnull, 'init', '--quiet', '--template=', str(work)],
        ['git', '-c', 'core.attributesFile=' + os.devnull, '-C', str(work), 'apply', '--check', str(patch)],
        ['git', '-c', 'core.attributesFile=' + os.devnull, '-C', str(work), 'apply', str(patch)],
    ):
        subprocess.run(command, env=env, check=True, timeout=30)
    candidate = target.read_bytes()
    require_sha(candidate, manifest['candidate_sha256'], 'rebuilt candidate')
    return candidate.decode('utf-8')


def translation_unit(package, candidate):
    # Replace dependency includes only; preserve every production implementation byte.
    for include in PROJECT_INCLUDES:
        if candidate.count(include) != 1:
            raise RuntimeError('Missing or duplicate dependency include: ' + include)
        candidate = candidate.replace(include, '// dependency provided by test shim: ' + include)
    return (package / 'shim.h').read_text() + '\n' + candidate + '\n' + (package / 'harness.c').read_text()


def restore_directory_permissions(root):
    # Read-only base fixtures must also clean up under an ordinary, unprivileged CI user.
    for directory, _, _ in os.walk(str(root), followlinks=False):
        os.chmod(directory, 0o700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-out', type=Path, help='write successful test summary to this path')
    parser.add_argument('--integrity-only', action='store_true',
                        help='portable production binding + four deliberate drift checks; no native execution')
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError('Python optimization disables test assertions; run without -O/PYTHONOPTIMIZE')
    if sys.platform != 'linux' and not args.integrity_only:
        raise RuntimeError('Native tests require Linux; this is a failure, never a skipped test')
    package = Path(__file__).resolve().parent
    manifest = json.loads((package / 'manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='bc7-overlay-') as temporary:
        root = Path(temporary)
        try:
            production = rebuild_production(package, root / 'production', manifest, require_sha)
            candidate = rebuild(package, root / 'rebuild', manifest)
            if production != candidate:
                raise RuntimeError('Production patch and independent cache patch disagree')
            print('PASS actual production linux.patch + original upstream fixture + exact C equality', flush=True)
            print('PASS SHA-bound fixture + git apply --check/apply + exact candidate SHA256', flush=True)
            integrity = run_integrity_checks(package, root, manifest, rebuild)
            results = []
            if not args.integrity_only:
                exe = root / 'harness'
                compiler = shlex.split(os.environ.get('CC', 'cc'))
                if not compiler:
                    raise RuntimeError('CC must name a C compiler')
                flags = ['-UNDEBUG', '-D_FILE_OFFSET_BITS=64', '-std=gnu11', '-O1', '-g',
                         '-Wall', '-Wextra', '-Werror', '-pthread', '-x', 'c', '-', '-o', str(exe)]
                subprocess.run(compiler + flags, input=translation_unit(package, candidate), text=True,
                               env=dict(os.environ, TMPDIR=str(root)), check=True, timeout=120)
                print('PASS native compile with {}'.format(shlex.join(compiler)), flush=True)
                # /dev/shm may be noexec: execute an anonymous in-memory copy via the
                # live parent's fd. Nothing is installed or executed from a project path.
                fd = os.memfd_create('bc7-overlay-harness', os.MFD_CLOEXEC)
                try:
                    with os.fdopen(os.dup(fd), 'wb') as stream:
                        stream.write(exe.read_bytes())
                    os.fchmod(fd, 0o700)
                    results = run_suite(Path('/proc/{}/fd/{}'.format(os.getpid(), fd)), root)
                finally:
                    os.close(fd)
                if len(results) != manifest['expected_test_groups']:
                    raise RuntimeError('Unexpected test count: {}'.format(len(results)))
            summary = {'platform': sys.platform, 'native_arch': platform.machine(),
                       'mode': 'integrity-only' if args.integrity_only else 'native',
                       'production_patch_bound': True,
                       'candidate_sha256': manifest['candidate_sha256'],
                       'passed': len(results), 'tests': results,
                       'integrity_checks_passed': len(integrity), 'integrity_checks': integrity,
                       'skipped': 0}

        finally:
            restore_directory_permissions(root)
    summary['temporary_files_cleaned'] = True
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
