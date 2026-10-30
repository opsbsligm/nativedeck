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
    probe='import fontTools; from compression import zstd; print(fontTools.__version__); raise SystemExit(0 if fontTools.__version__ == "4.60.1" else 1)'
    if target.exists():
        if target.is_symlink():raise ValueError('Refusing a symlinked Python environment')
        subprocess.run([str(target/'bin/python3'),'-c',probe],check=True)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    wheel=target.parent/'fonttools-4.60.1-py3-none-any.whl'
    if wheel.exists():raise FileExistsError('Refusing to overwrite cached wheel')
    print('Project-local UI Python: peak estimate 100MiB; no system package changes',flush=True)
    url='https://files.pythonhosted.org/packages/c7/93/0dd45cd283c32dea1545151d8c3637b4b8c53cdb3a625aeb2885b184d74d/fonttools-4.60.1-py3-none-any.whl'
    expected='906306ac7afe2156fcf0042173d6ebbb05416af70f6b370967b47f8f00103bbb'
    with urllib.request.urlopen(url,timeout=45) as stream:body=stream.read(2*1024*1024+1)
    if len(body)!=1143175 or hashlib.sha256(body).hexdigest()!=expected:raise ValueError('Incorrect public fontTools wheel')
    created=False;wheel_created=False
    try:
        with wheel.open('xb') as stream:stream.write(body)
        wheel_created=True
        target.mkdir();created=True
        venv.EnvBuilder(with_pip=True,symlinks=False).create(target)
        subprocess.run([str(target/'bin/python3'),'-m','pip','install','--disable-pip-version-check',
                        '--no-index','--no-deps',str(wheel)],check=True)
        subprocess.run([str(target/'bin/python3'),'-c',probe],check=True)
        print(json.dumps({'python_environment':str(target),'fonttools':'4.60.1','wheel_sha256':expected,
                          'game_resources_generated':False}))
    except BaseException:
        if created:shutil.rmtree(target)
        raise
    finally:
        if wheel_created:wheel.unlink(missing_ok=True)


if __name__=='__main__':main()
