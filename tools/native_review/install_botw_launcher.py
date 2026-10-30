"""Atomically install or roll back only the reviewed BOTW launcher, never the game."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from botw_launch import preflight

OLD = '60ebdbc427d8ee4f3a37efca5d3840e5fd5228d692f8feda463d4167c1ed8848'
DEFAULTS = '098fedcb94985ba97d2d38dbf020086b7275163e2cc1eaa0c4883f26fd90aa9a'
PREVIOUS_HELPER = 'fddcd0517b288d1c45f74470a790067d8fbcfa1d550ca81c05156c3e84ed73e7'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.botw-launch-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        if path.read_bytes() != data:
            raise ValueError('Installed file readback mismatch')
    finally:
        Path(name).unlink(missing_ok=True)


def install(rollback=False):
    source = Path(__file__).resolve().parent
    root = Path.home()/'native-recomp/swr'
    evidence = root.parent/'evidence/botw-refine-20261030'
    target = root/'run.sh'
    before = target.read_bytes()
    shell = (source/'botw-run.sh').read_bytes()
    helper = (source/'botw_launch.py').read_bytes()
    evidence.mkdir(parents=True, exist_ok=True)
    backup = evidence/'run.sh.before'
    if rollback:
        old = backup.read_bytes()
        if sha(old) != OLD or before != shell:
            raise ValueError('Rollback inputs no longer match; refusing to overwrite')
        atomic(target, old, 0o755)
        print(json.dumps({'rolled_back': True, 'launcher_sha256': sha(old)}))
        return
    if sha(before) not in (OLD, sha(shell)):
        raise ValueError('Launcher changed since review; refusing to overwrite')
    if sha((root/'settings_defaults.py').read_bytes()) != DEFAULTS:
        raise ValueError('Defaults helper changed since review')
    preflight(root)
    subprocess.run(['bash', '-n', str(source/'botw-run.sh')], check=True)
    compile(helper, 'botw_launch.py', 'exec')
    if backup.exists():
        if sha(backup.read_bytes()) != OLD:
            raise ValueError('Rollback backup checksum mismatch')
    else:
        if sha(before) != OLD:
            raise ValueError('Original launcher backup is missing')
        with backup.open('xb') as stream:
            stream.write(before)
            stream.flush()
            os.fsync(stream.fileno())
    if sha(backup.read_bytes()) != OLD:
        raise ValueError('Original launcher backup readback mismatch')
    installed = root/'botw_launch.py'
    if installed.exists() and installed.read_bytes() != helper:
        previous = installed.read_bytes()
        if sha(previous) != PREVIOUS_HELPER:
            raise ValueError('A different launch helper already exists')
        helper_backup = evidence/('botw_launch-'+PREVIOUS_HELPER[:12]+'.before.py')
        if not helper_backup.exists():
            with helper_backup.open('xb') as stream:
                stream.write(previous)
        if helper_backup.read_bytes() != previous:
            raise ValueError('Previous helper backup readback mismatch')
    atomic(installed, helper, 0o644)
    if target.read_bytes() != before:
        raise ValueError('Launcher changed during installation')
    atomic(target, shell, 0o755)
    result = {'installed': True, 'game_restarted': False, 'game_binary_changed': False,
              'launcher_sha256': sha(shell), 'helper_sha256': sha(helper), 'rollback': str(backup)}
    record = evidence/('install-'+sha(shell)[:12]+'-'+sha(helper)[:12]+'.json')
    if not record.exists():
        with record.open('x') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback', action='store_true')
    install(parser.parse_args().rollback)
