"""Build only the three gyro objects, then bind the linked ELF to its inputs."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import resource
import subprocess

root = Path.home() / 'native-recomp'
candidate = root / 'work/totk-1.4.3-20261031/gyro-20261103'
report = root / 'evidence/gyro-20261103'
report.mkdir(parents=True, exist_ok=True)


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


if __name__ == '__main__':
    prepared = json.loads((candidate / 'prepare.json').read_text())
    inputs = {name: sha(candidate / name) for name in [
        'window_sdl.c', 'deck_motion.h', 'deck_motion_decode.c', 'deck_motion_linux.c',
        'build.ninja', 'prepare.json']}
    for path, expected in prepared['immutable_object_hashes'].items():
        if sha(Path(path)) != expected:
            raise ValueError('Delivered linker input changed: ' + path)
    print('Three objects + native link; peak extra disk <0.9 GiB, one compiler, 4 GiB address limit.', flush=True)
    # The container inherits the process resource limits; no unquoted shell command.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    with (report / 'build-final.log').open('w') as log:
        subprocess.run(['distrobox', 'enter', '-n', 'nativedeck-build', '--', 'nice', '-n', '19',
                        'ninja', '-j1', '-f', str(candidate / 'build.ninja'),
                        str(candidate / 'ultratears')], stdout=log, stderr=subprocess.STDOUT, check=True)
    for name, expected in inputs.items():
        if sha(candidate / name) != expected:
            raise ValueError('Input changed during build: ' + name)
    receipt = {'at': datetime.now().astimezone().isoformat(),
               'binary_sha256': sha(candidate / 'ultratears'), 'inputs': inputs}
    (candidate / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'binary_sha256': receipt['binary_sha256'], 'build_receipt': True}))
