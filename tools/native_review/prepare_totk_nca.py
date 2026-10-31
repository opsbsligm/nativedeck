"""Prepare the supported TOTK 1.0.0 data directly from a local program NCA.

The existing recompiler accepts --skip-extract after this step. No XCI wrapper,
download, game code or key is included in this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT/'ports/totk-recomp-linux/expected-v1.0.0.json'
REQUIRED_NCA_BYTES = 17148870656
REQUIRED_CONTENT_ID = '9d827368992a2faafa9062aa5458b7ec'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(8*1024*1024):
            h.update(block)
    return h.hexdigest()


def read_keys(path):
    keys = {}
    for line in path.read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'([A-Za-z0-9_]+)\s*=\s*([0-9A-Fa-f]+)', line)
        if not match:
            continue
        name, value = match[1].lower(), match[2].lower()
        if len(value) not in (32, 64):
            continue
        if name in keys and keys[name] != value:
            raise ValueError('Conflicting duplicate key name: '+name)
        keys[name] = value
    if len(keys.get('header_key', '')) != 64:
        raise ValueError('A 32-byte header_key is required')
    direct = len(keys.get('key_area_key_application_0e', '')) == 32
    derived = all(len(keys.get(n, '')) == 32 for n in (
        'master_key_0e', 'key_area_key_application_source',
        'aes_kek_generation_source', 'aes_key_generation_source'))
    if not (direct or derived):
        raise ValueError('Missing generation 0E application key or complete master-key derivation inputs')
    return keys


def write_filtered_keys(path, keys):
    with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as out:
        for name, value in sorted(keys.items()):
            out.write(name+' = '+value+'\n')


def validate_extraction(folder, pin):
    expected = pin['exefs_sha256']
    actual = {}
    for name, wanted in expected.items():
        path = folder/'exefs'/name
        if not path.is_file() or path.is_symlink() or digest(path) != wanted:
            raise ValueError('Extracted ExeFS does not match TOTK 1.0.0: '+name)
        actual[name] = wanted
    romfs = folder/'romfs'
    required = ('System/Resource/ResourceSizeTable.Product.100.rsizetable.zs',
                'Font/Font.Nin_NX_NVN.bfarc.zs')
    if any(not (romfs/name).is_file() for name in required):
        raise ValueError('The supported 1.0.0 RomFS is incomplete')
    movies = sorted(romfs.rglob('*.webm'))
    return {'version': '1.0.0', 'exefs_sha256': actual,
            'movie_files': len(movies), 'hardware_validated': False}


def prepare(nca, keys_file, hactool, destination, check_only=False):
    nca, keys_file, hactool = map(lambda p: Path(p).absolute(), (nca, keys_file, hactool))
    destination = Path(destination).absolute()
    # Fail on unavailable key material before reading seventeen GB or creating output.
    keys = read_keys(keys_file)
    if nca.is_symlink() or not nca.is_file() or nca.stat().st_size != REQUIRED_NCA_BYTES:
        raise ValueError('Use the complete, unwrapped 1.0.0 program NCA')
    if check_only:
        return {'key_inputs_present': True, 'nca_size_matches': True,
                'content_hash_verified': False, 'hardware_validated': False}
    workspace = (Path.home()/'native-recomp').resolve()
    if destination.exists() or destination.is_symlink() or not destination.parent.resolve().is_relative_to(workspace):
        raise ValueError('Use a new data directory inside ~/native-recomp')
    if not hactool.is_file() or not os.access(hactool, os.X_OK):
        raise ValueError('A runnable local hactool is required')
    pin = json.loads(PIN.read_text())
    if pin.get('title_id') != '0100F2C0115B6000' or pin.get('program_nca') != REQUIRED_CONTENT_ID+'.nca':
        raise ValueError('Unexpected game fingerprint profile')
    before = nca.stat()
    print('Hashing complete local program NCA', flush=True)
    nca_hash = digest(nca)
    if not nca_hash.startswith(REQUIRED_CONTENT_ID):
        raise ValueError('NCA full SHA does not match the original content ID')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 22*1024**3:
        raise ValueError('At least 22 GiB free is required for extracted data')
    stage = Path(tempfile.mkdtemp(prefix='.totk-100-extract-', dir=destination.parent))
    os.chmod(stage, 0o700)
    private_keys = stage/'keys.filtered'
    try:
        write_filtered_keys(private_keys, keys)
        for name in ('exefs', 'romfs'):
            (stage/name).mkdir()
        print('Verifying and extracting local content; estimated peak 18 GiB', flush=True)
        log = stage/'hactool.log'
        with log.open('xb') as output:
            result = subprocess.run([str(hactool), '--suppresskeys', '--verify',
                '-k', str(private_keys), '-t', 'nca', '--exefsdir='+str(stage/'exefs'),
                '--romfsdir='+str(stage/'romfs'), str(nca)],
                stdout=output, stderr=subprocess.STDOUT, check=False)
        private_keys.unlink()
        text = log.read_text(errors='replace')
        if result.returncode or re.search(r'\b(?:FAIL|FAILURE|FAILED|INVALID)\b', text, re.I):
            raise ValueError('hactool verification/extraction failed; output is not publishable')
        record = validate_extraction(stage, pin)
        after = nca.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('Input NCA changed during preparation')
        record.update(source_nca_sha256=nca_hash, content_id=REQUIRED_CONTENT_ID,
                      hactool_sha256=digest(hactool), source_unchanged=True)
        (stage/'native-input.json').write_text(json.dumps(record, indent=2)+'\n')
        from ultratears_bundle import publish_no_replace
        publish_no_replace(stage, destination)
        return record
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nca', 'keys', 'hactool', 'destination'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.nca, args.keys, args.hactool,
                                 args.destination, args.check_only), indent=2))
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, str(exc)+'\n')
