"""Prepare checked local 1.4.3 input for the native Linux build (no decryption).

Each stage is explicit: check, lift, romfs. Run only when existing games are idle.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from linux_inputs import BASES, ROOT, check_exefs, expected, seal_generated


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dump', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--stage', choices=('check', 'lift', 'romfs'), default='check')
    a = p.parse_args()
    try:
        check_exefs(a.dump / 'exefs')
        if not (a.dump / 'romfs/Pack/ZsDic.pack.zs').is_file():
            p.error('Missing extracted TOTK RomFS (Pack/ZsDic.pack.zs)')
        if a.stage == 'check':
            print('TOTK 1.4.3 code identity verified; RomFS content validation requires --stage romfs')
            return
        a.data.mkdir(parents=True, exist_ok=True)
        if a.stage == 'lift':
            out = a.data / 'generated'
            out.mkdir(exist_ok=True)
            (out / 'manifest-linux.json').unlink(missing_ok=True)
            for module, (base, _) in BASES.items():
                directory = out / module
                directory.mkdir(exist_ok=True)
                with (out / (module + '.log')).open('w') as log:
                    subprocess.run([sys.executable, '-X', 'faulthandler', str(ROOT/'tools/lifter/gen.py'),
                                    module, str((a.dump/'exefs'/module).resolve()), hex(base), str(directory),
                                    '--simd', 'c'], stdout=log, stderr=subprocess.STDOUT, check=True)
                print('Lifted ' + module, flush=True)
            files = seal_generated(out, a.dump / 'exefs')
            print('Verified generated source files:', len(files))
        else:
            from pack_romfs import pack
            n, size, content = pack(a.dump / 'romfs', a.data / 'romfs', threads=1, progress=print)
            want = expected()
            if n != want['ROMFS_FILES'] or size < want['ROMFS_BYTES'] or content != want['ROMFS_CONTENT']:
                p.error('RomFS differs from upstream 1.4.3 content fingerprint')
            print('RomFS content verified:', content)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
