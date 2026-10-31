# SPDX-License-Identifier: GPL-3.0-or-later
"""Deliberate drift must fail before a different cache implementation is tested."""
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess


def run_integrity_checks(package, root, manifest, rebuild):
    results = []
    for kind in ('fixture', 'patch', 'candidate', 'nonapplicable-hunk'):
        case = root / ('binding-' + kind)
        copied = case / 'package'
        shutil.copytree(str(package), str(copied))
        for path in copied.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        copied.chmod(0o700)
        changed = copy.deepcopy(manifest)
        if kind == 'fixture':
            path = copied / manifest['fixture']
            path.write_bytes(path.read_bytes() + b'\n/* source drift */\n')
        elif kind == 'patch':
            path = copied / manifest['patch']
            path.write_bytes(path.read_bytes() + b'\n')
        elif kind == 'candidate':
            changed['candidate_sha256'] = '0' * 64
        else:
            path = copied / manifest['patch']
            data = path.read_bytes()
            old = b'-static FILE *g_pack, *g_idx;'
            if data.count(old) != 1:
                raise RuntimeError('Expected a single patch context for integrity test')
            path.write_bytes(data.replace(old, b'-static FILE *not_the_upstream_context;'))
            changed['patch_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            rebuild(copied, case / 'rebuild', changed)
        except RuntimeError as error:
            if kind == 'nonapplicable-hunk' or 'SHA256 mismatch' not in str(error):
                raise
        except subprocess.CalledProcessError:
            if kind != 'nonapplicable-hunk':
                raise
        else:
            raise RuntimeError('Integrity check accepted intentional drift: ' + kind)
        name = 'reject deliberate ' + kind + ' drift'
        results.append(name)
        print('PASS ' + name, flush=True)
    return results
