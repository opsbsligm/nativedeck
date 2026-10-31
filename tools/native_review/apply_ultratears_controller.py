"""Apply authored Steam Deck art after the pinned Linux source port.

Only the known renderer unit and its new bitmap header are changed. Actual game
rendering, labels, layout guides and controls still require hardware acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ART = Path(__file__).resolve().parents[2]/'ports/ultratears-linux/controller-runtime'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(source):
    source = Path(source).absolute()
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Use a real isolated Linux source directory')
    target = source/'src/gfx/vkb_tex.c'
    header = target.with_name('totk_deck_bitmaps.h')
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(source.resolve()):
        raise ValueError('Renderer must be a regular file inside the source tree')
    proof = json.loads((ART/'controller-hook-build.json').read_text())
    if digest(ART/'totk_deck_bitmaps.h') != proof['header_sha256']:
        raise ValueError('Authored bitmap header changed')
    if digest(target) == proof['runtime_after_sha256']:
        if header.is_symlink() or not header.is_file() or digest(header) != proof['header_sha256']:
            raise ValueError('Installed controller header does not match the renderer')
        return {'reused': True, 'hardware_validated': False}
    if digest(target) != proof['runtime_before_sha256'] or header.exists() or header.is_symlink():
        raise ValueError('Unexpected source state; apply the pinned Linux port first')
    patch = ART/'steamdeck-controller.patch'
    command = ['git', '-C', str(source), 'apply', '--include=src/gfx/vkb_tex.c']
    subprocess.run([*command, '--check', str(patch)], check=True)
    before = target.read_bytes()
    try:
        shutil.copyfile(ART/'totk_deck_bitmaps.h', header)
        subprocess.run([*command, str(patch)], check=True)
        if digest(target) != proof['runtime_after_sha256'] or digest(header) != proof['header_sha256']:
            raise ValueError('Applied renderer/artwork identity differs from the checked source')
    except BaseException:
        target.write_bytes(before)
        header.unlink(missing_ok=True)
        raise
    return {'reused': False, 'source_sha256': proof['runtime_after_sha256'],
            'display_art': 'unified-steamdeck-inclined', 'requires_rebuild': True,
            'hardware_validated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.source)))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error)+'\n')
