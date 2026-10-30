"""Apply the NativeDeck source port to the exact clean public UltraTears commit."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

PORT = Path(__file__).resolve().parents[2] / 'ports/ultratears-linux'
UPSTREAM = '0c9ce8afd4c3ab81c33200917af51fb9807aeef0'


def apply(source):
    source = Path(source).resolve()
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != UPSTREAM:
        raise ValueError('Use public UltraTears commit ' + UPSTREAM)
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']):
        raise ValueError('Source checkout is dirty; use an isolated clean checkout')
    patch = PORT / 'linux.patch'
    files = sorted(p for p in (PORT / 'overlay').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for p in files:
        target = source / p.relative_to(PORT / 'overlay')
        if target.exists():
            raise ValueError('Refusing to overwrite ' + str(target))
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', '--whitespace=nowarn', str(patch)], check=True)
    for p in files:
        target = source / p.relative_to(PORT / 'overlay')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    return dict(upstream=head, overlay_files=len(files), game_content_included=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(apply(a.source)))
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
