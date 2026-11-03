"""Install the checked V8 motion candidate while its normal profile is idle."""
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.home() / 'native-recomp'
BUNDLE = ROOT / 'ultratears/releases/v143-20261031-first'
CANDIDATE = ROOT / 'work/totk-1.4.3-20261031/gyro-20261103'
REPORT = ROOT / 'evidence/gyro-20261103'
PARENT = 'f10b228eac91a34cfaf4b54cdc589c96be62c8aa71432c93672d0b4ee218feca'
PROFILE = Path.home() / '.local/share/ultratears/test-profiles/v8-opening-20261102/ultratears'
LAUNCHER = ROOT / 'launchers/totk-steam.sh'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def replace_file(source, target):
    stage = target.with_name(target.name + '.gyro-stage')
    require(not stage.exists(), 'An earlier install stage needs reconciliation')
    try:
        with source.open('rb') as incoming, stage.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        shutil.copymode(target, stage)
        os.replace(stage, target)
    finally:
        stage.unlink(missing_ok=True)


def main():
    require(subprocess.run(['pgrep', '-x', 'ultratears'], stdout=subprocess.DEVNULL).returncode == 1,
            'Exit the existing native game before deployment')
    require(shutil.disk_usage(ROOT).free > 3 * 1024**3, 'Insufficient staging and rollback space')
    require(sha(BUNDLE / 'ultratears') == PARENT, 'Deployed parent ELF changed')
    prepared = json.loads((CANDIDATE / 'prepare.json').read_text())
    require(prepared['parent_elf_sha256'] == PARENT, 'Candidate parent mismatch')
    for name, expected in prepared['source_hashes'].items():
        require(sha(CANDIDATE / name) == expected, 'Candidate source changed: ' + name)
    require(sha(CANDIDATE / 'window_sdl.c') == prepared['candidate_window_sha256'],
            'Candidate SDL integration changed')
    built = json.loads((CANDIDATE / 'build-receipt.json').read_text())
    new_sha = sha(CANDIDATE / 'ultratears')
    require(built['binary_sha256'] == new_sha, 'Linked ELF changed since build')
    for name, expected in built['inputs'].items():
        require(sha(CANDIDATE / name) == expected, 'Build input changed: ' + name)
    record = json.loads((BUNDLE / 'build-inputs/build-record.json').read_text())
    require(record['binary_sha256'] == PARENT, 'Installed build record mismatch')
    with (PROFILE / 'session.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(subprocess.run(['pgrep', '-x', 'ultratears'], stdout=subprocess.DEVNULL).returncode == 1,
                'Native game started during preflight')
        production = Path.home() / '.local/share/ultratears/userdata'
        before = inventory(PROFILE / 'userdata')
        production_before = inventory(production)
        backup = REPORT / 'backup'
        require(not backup.exists(), 'Backup already exists; reconcile before retrying')
        backup.mkdir(parents=True)
        shutil.copytree(PROFILE / 'userdata', backup / 'profile-userdata')
        require(inventory(backup / 'profile-userdata') == before, 'Save backup mismatch')
        targets = {'ultratears': BUNDLE / 'ultratears', 'bundle.json': BUNDLE / 'bundle.json',
                   'build-inputs/build-record.json': BUNDLE / 'build-inputs/build-record.json',
                   'totk-steam.sh': LAUNCHER}
        for name, target in targets.items():
            dest = backup / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            require(sha(dest) == sha(target), 'Rollback copy mismatch')
        record['binary_sha256'] = new_sha
        record['native_gyro'] = {'mode': 'read-only-Deck-IMU-fallback', 'parent_elf_sha256': PARENT,
                                'source_sha256': prepared['source_hashes'],
                                'window_sha256': prepared['candidate_window_sha256'],
                                'prepare_sha256': sha(CANDIDATE / 'prepare.json'),
                                'physical_axis_tested': False, 'aiming_validated': False}
        record_path = REPORT / 'new-build-record.json'
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        manifest = json.loads((BUNDLE / 'bundle.json').read_text())
        for name, source in [('ultratears', CANDIDATE / 'ultratears'),
                             ('build-inputs/build-record.json', record_path)]:
            manifest['files'][name].update(sha256=sha(source), bytes=source.stat().st_size)
        manifest_path = REPORT / 'new-bundle.json'
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        candidate_launcher = CANDIDATE / 'totk-steam.sh'
        require('export TOTK_GYRO=1\n' in candidate_launcher.read_text(), 'Normal gyro launch flag missing')
        try:
            for source, target in [(CANDIDATE / 'ultratears', targets['ultratears']),
                                   (record_path, targets['build-inputs/build-record.json']),
                                   (manifest_path, targets['bundle.json']),
                                   (candidate_launcher, LAUNCHER)]:
                replace_file(source, target)
            subprocess.run([sys.executable, str(BUNDLE / 'verify_ultratears_bundle.py'),
                            '--root', str(BUNDLE), '--quiet'], check=True)
            require(sha(BUNDLE / 'ultratears') == new_sha, 'Installed ELF differs')
            require(inventory(PROFILE / 'userdata') == before and inventory(production) == production_before,
                    'Save inventory changed during install')
        except Exception:
            for name, target in targets.items():
                replace_file(backup / name, target)
            raise
        receipt = {'at': datetime.now().astimezone().isoformat(), 'elf_sha256': new_sha,
                   'parent_elf_sha256': PARENT, 'save_files': len(before), 'saves_unchanged': True,
                   'production_saves_unchanged': True, 'backup': str(backup),
                   'hardware_validated': False, 'playability_validated': False, 'physical_axis_tested': False}
        (REPORT / 'install.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
