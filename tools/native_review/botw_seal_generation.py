"""Seal/check this run's generated files, so a linker retry never reuses an older game's code."""
import hashlib
import argparse
import json
import os
import sys
from pathlib import Path

root=Path.home()/'native-recomp'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work',type=Path,default=Path(os.environ.get('BOTW_FRESH_WORK',str(root/'work/botw-complete-20261030'))))
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
work=args.work.resolve()
source=work/'source'
manifest=work/'generation-seal.json'
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()
inputs={p.name:digest(p) for p in (source/'extracted/exefs').iterdir() if p.is_file()}
files=sorted((source/'generated').rglob('*.c'))
if len(files)<1000 or any(not list((source/'generated'/name).glob('*.c')) for name in ['main','subsdk0','sdk']):
    raise ValueError('Full module generation is missing')
generator_names=['tools/gen.py','tools/lifter.py','tools/analyze.py','tools/nso.py','tools/passes.py','tools/patches.py',
                 'tools/simd_c.py','tools/gamelib_entry.c','tools/layout.py','tools/game_sites.py','tools/legacy_sdk7.py',
                 'runtime/cpu.h','runtime/simd.h','runtime/simd_fp.h','runtime/simd_softfma.h','runtime/gamelib.h','runtime/hle/hle_symbols.txt']
value={'inputs':inputs,'generator':{name:digest(source/name) for name in generator_names},
       'generated':{p.relative_to(source).as_posix():digest(p) for p in files}}
if args.check:
    if json.loads(manifest.read_text())!=value:raise ValueError('Generated code or its inputs changed; no cache reuse permitted')
else:
    evidence=Path(os.environ.get('BOTW_FRESH_EVIDENCE',str(root/'evidence/botw-complete-20261030')))
    log=(evidence/'fresh-build.log').read_text(errors='replace')
    if 'FRESH_GENERATION_DONE' not in log:raise ValueError('No complete generation result')
    with manifest.open('x') as stream:json.dump(value,stream,sort_keys=True)
print('FRESH_GENERATION_SEAL',len(files),'source files verified',flush=True)
