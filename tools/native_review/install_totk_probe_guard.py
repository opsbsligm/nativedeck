"""Protect the old ROM-free runtime probe from being mistaken for a game build."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from native_binary_check import inspect


def install():
    root = Path.home()/'native-recomp'
    package = root/'dist/totk-recomp'
    evidence = root/'evidence/review-20261030'
    result = inspect(package/'totk', True)
    if result['function_counters'].get('g_ftab_count') != 0:
        raise ValueError('Current binary is not the reviewed empty probe; do not replace its launcher')
    launcher = package/'run.sh'
    old = launcher.read_bytes()
    marker = 'mkdir -p "$state/userdata" "$state/run"\n'
    if old.decode().count(marker) != 1:
        raise ValueError('Unexpected launcher; review it first')
    with (evidence/'totk-run.sh.before-guard').open('xb') as stream:
        stream.write(old)
    guard = '''if ! python3 "$here/native_binary_check.py" "$here/totk" --totk > "$state/run/native-build-check.json"; then
  echo "尚未完成游戏构建，暂不能启动。" >&2
  exit 1
fi
'''
    text = old.decode().replace(marker, marker+guard)
    shutil.copy2(Path(__file__).with_name('native_binary_check.py'), package/'native_binary_check.py')
    candidate = package/'run.sh.guard-new'
    with candidate.open('x') as stream:
        stream.write(text)
    candidate.chmod(launcher.stat().st_mode & 0o777)
    subprocess.run(['bash', '-n', str(candidate)], check=True)
    candidate.replace(launcher)
    if launcher.read_text() != text:
        raise ValueError('Launcher readback mismatch')
    result['launcher_sha256'] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    with (evidence/'totk-probe-guard.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    install()
