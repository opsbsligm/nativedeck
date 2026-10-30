"""Prepare a project-local Python environment for the pinned public icon generator."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import venv


def main():
    if sys.platform!='linux' or sys.version_info<(3,14):
        raise RuntimeError('Native Linux Python >=3.14 with compression.zstd is required')
    from compression import zstd  # Verify the interpreter, not a replacement runtime.
    del zstd
    target=Path.home()/'native-recomp/deps/ui-python'
    probe='import fontTools; from compression import zstd; print(fontTools.__version__); raise SystemExit(0 if fontTools.__version__ == "4.68.0" else 1)'
    if target.exists():
        if target.is_symlink():raise ValueError('Refusing a symlinked Python environment')
        subprocess.run([str(target/'bin/python3'),'-c',probe],check=True)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    wheel=target.parent/'fonttools-4.68.0-py3-none-any.whl'
    if wheel.exists():raise FileExistsError('Refusing to overwrite cached wheel')
    print('Project-local UI Python: peak estimate 100MiB; no system package changes',flush=True)
    url='https://files.pythonhosted.org/packages/35/74/4ea331ecc65ba05a58b1e4e8ccd604c8a15565f876dfbf93fc2a2ea2e22b/fonttools-4.68.0-py3-none-any.whl'
    expected='d76f8fdcb6936f5e1045a0c9dd721a4bf11112e60d1e243bfa1d39f06a8b3104'
    requirements=Path(__file__).resolve().parent/'xbox/requirements.txt'
    if requirements.read_text().strip()!='fonttools==4.68.0 --hash=sha256:'+expected:
        raise ValueError('UI dependency manifest differs from the pinned wheel')
    with urllib.request.urlopen(url,timeout=45) as stream:body=stream.read(2*1024*1024+1)
    if len(body)!=1248357 or hashlib.sha256(body).hexdigest()!=expected:raise ValueError('Incorrect public fontTools wheel')
    created=False;wheel_created=False
    try:
        with wheel.open('xb') as stream:stream.write(body)
        wheel_created=True
        target.mkdir();created=True
        venv.EnvBuilder(with_pip=True,symlinks=False).create(target)
        subprocess.run([str(target/'bin/python3'),'-m','pip','install','--disable-pip-version-check',
                        '--no-index','--no-deps','--require-hashes','--find-links',str(wheel.parent),
                        '-r',str(requirements)],check=True)
        subprocess.run([str(target/'bin/python3'),'-c',probe],check=True)
        print(json.dumps({'python_environment':str(target),'fonttools':'4.68.0','wheel_sha256':expected,
                          'game_resources_generated':False}))
    except BaseException:
        if created:shutil.rmtree(target)
        raise
    finally:
        if wheel_created:wheel.unlink(missing_ok=True)


if __name__=='__main__':main()
