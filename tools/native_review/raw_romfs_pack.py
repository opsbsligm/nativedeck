"""把经过校验的 Nintendo RomFS 映像转为既有原生运行时格式，不落盘三十万个文件。"""
import argparse
import ast
import hashlib
import json
import os
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import time

SENTINEL = 0xffffffff


def read_entries(image):
    if image.is_symlink() or not image.is_file():
        raise ValueError('Use a regular raw RomFS image')
    size = image.stat().st_size
    with image.open('rb') as stream:
        header = stream.read(80)
        if len(header) != 80:
            raise ValueError('Short RomFS header')
        values = struct.unpack('<10Q', header)
        if values[0] != 80:
            raise ValueError('Unsupported RomFS header')
        _, dh, dn, dt, dsize, fh, fn, ft, fsize, data = values
        if not (80 <= data <= size and dsize <= 128*1024**2 and fsize <= 256*1024**2):
            raise ValueError('RomFS metadata exceeds bounds')
        regions = sorted((at, at+length) for at, length in
                         ((dh,dn),(dt,dsize),(fh,fn),(ft,fsize)))
        for at, end in regions:
            if at < 80 or at > size or end > size:
                raise ValueError('Invalid RomFS metadata range')
        if any(left[1] > right[0] for left, right in zip(regions, regions[1:])):
            raise ValueError('Overlapping RomFS metadata tables')
        if any(at <= data < end for at, end in regions):
            raise ValueError('RomFS data begins inside metadata')
        # Nintendo permits metadata either before or after the file payload.
        payload_end = min([at for at, end in regions if at >= data] + [size])
        stream.seek(dt); directories = stream.read(dsize)
        stream.seek(ft); files = stream.read(fsize)
    if len(directories) != dsize or len(files) != fsize:
        raise ValueError('Truncated RomFS metadata')

    def entry_name(blob, at, fixed, length):
        if at > len(blob) or fixed > len(blob)-at or length > len(blob)-at-fixed:
            raise ValueError('RomFS name exceeds metadata')
        name = blob[at+fixed:at+fixed+length].decode('utf-8')
        if not name or name in ('.','..') or any(c in name for c in ('/','\\','\0')):
            raise ValueError('Unsafe RomFS name')
        return name

    pending = [(0,'',None)]
    seen_dirs, seen_files, paths = set(), set(), set()
    output = []
    directory_paths = {''}
    while pending:
        at, prefix, parent = pending.pop()
        if at in seen_dirs or at > len(directories)-24:
            raise ValueError('Cyclic or truncated RomFS directory')
        seen_dirs.add(at)
        up, sibling, child, first, _, length = struct.unpack_from('<6I',directories,at)
        if parent is not None:
            if up != parent:
                raise ValueError('Directory parent mismatch')
            name = entry_name(directories,at,24,length)
            prefix = prefix+'/'+name if prefix else name
            if prefix in directory_paths or prefix in paths:
                raise ValueError('Duplicate directory or file/directory path collision')
            directory_paths.add(prefix)
        elif length != 0:
            raise ValueError('Invalid RomFS root')
        cursor = first
        while cursor != SENTINEL:
            if cursor in seen_files or cursor > len(files)-32:
                raise ValueError('Cyclic or truncated RomFS file')
            seen_files.add(cursor)
            up, following, offset, length, _, n = struct.unpack_from('<IIQQII',files,cursor)
            if up != at:
                raise ValueError('File parent mismatch')
            name = entry_name(files,cursor,32,n)
            path = prefix+'/'+name if prefix else name
            absolute = data+offset
            if path in paths or path in directory_paths or absolute > payload_end or length > payload_end-absolute:
                raise ValueError('Duplicate path or file outside RomFS')
            paths.add(path)
            output.append({'path':path,'raw_offset':absolute,'size':length})
            if len(output)>500000:
                raise ValueError('RomFS file limit exceeded')
            cursor = following
        siblings = set()
        while child != SENTINEL:
            if child in siblings or child > len(directories)-24:
                raise ValueError('Cyclic RomFS child list')
            siblings.add(child)
            pending.append((child,prefix,at))
            if len(pending)+len(seen_dirs)>500000:
                raise ValueError('RomFS directory limit exceeded')
            child = struct.unpack_from('<I',directories,child+4)[0]
        if len(output)>500000 or len(seen_dirs)>500000:
            raise ValueError('RomFS entry limit exceeded')
    return sorted(output,key=lambda row:row['path'])


def pack(image, destination, expected, index_script, progress=print):
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a new native resource directory')
    validate_profile(expected)
    if index_script.is_symlink() or not index_script.is_file():
        raise ValueError('Use a local regular index script')
    before = image.stat()
    rows = read_entries(image)
    if len(rows) != expected['romfs_files']:
        raise ValueError('RomFS version/file count mismatch')
    part = destination.with_name(destination.name+'.partial')
    part.mkdir()
    try:
        index, cursor, processed = [],0,0
        content = hashlib.sha256()
        last = time.monotonic()
        with image.open('rb',buffering=1024*1024) as source, (part/'romfs.bin').open('xb',buffering=1024*1024) as output:
            for number,row in enumerate(rows,1):
                pad = -cursor % 16
                if pad:
                    output.write(bytes(pad));cursor+=pad
                index.append({'path':row['path'],'offset':cursor,'size':row['size']})
                if source.tell()!=row['raw_offset']:
                    source.seek(row['raw_offset'])
                digest = hashlib.sha256()
                remaining = row['size']
                while remaining:
                    block = source.read(min(1024*1024,remaining))
                    if not block:
                        raise ValueError('Short raw RomFS read')
                    output.write(block);digest.update(block)
                    remaining-=len(block);cursor+=len(block);processed+=len(block)
                content.update(digest.digest())
                if time.monotonic()-last>=20:
                    progress(json.dumps({'phase':'native-romfs-pack','files':number,'total_files':len(rows),'payload_bytes':processed}))
                    last=time.monotonic()
        if cursor < expected['romfs_bytes'] or content.hexdigest()!=expected['romfs_content']:
            raise ValueError('Full original resource fingerprint mismatch')
        after = image.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
            raise ValueError('Raw RomFS changed while packing')
        document={'status':'pass','source':'verified-raw-romfs','content_sha256':content.hexdigest(),'files':index}
        with (part/'index.json').open('x') as stream:
            json.dump(document,stream)
        subprocess.run([sys.executable, '-B', str(index_script.resolve()), str(part.resolve())],
                           check=True, stdout=subprocess.DEVNULL,
                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        runtime_index = part / 'runtime-index.bin'
        if runtime_index.is_symlink() or not runtime_index.is_file():
            raise ValueError('Index tool did not produce a regular runtime-index.bin')
        if destination.exists() or destination.is_symlink():
            raise ValueError('Destination appeared while packing')
        part.rename(destination)
        return {'files':len(rows),'bytes':cursor,'content_sha256':content.hexdigest(),
                'image':str(destination/'romfs.bin'),'hardware_validated':False}
    except BaseException:
        shutil.rmtree(part)
        raise


def validate_profile(expected):
    """Keep the existing profile's byte floor and full-content fingerprint gates."""
    for key in ('romfs_files', 'romfs_bytes'):
        if type(expected.get(key)) is not int or expected[key] < 0:
            raise ValueError('Invalid profile field: ' + key)
    if expected['romfs_files'] > 500000:
        raise ValueError('Profile exceeds file limit')
    digest = expected.get('romfs_content')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('Invalid profile field: romfs_content')


def load_profile(source):
    """Read the pinned local 1.4.3 GAME literal without importing/executing it."""
    if source.is_symlink() or not source.is_file():
        raise ValueError('Use a local regular profile source')
    definitions = [node.value for node in ast.parse(source.read_text(encoding='utf-8')).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'GAME' for t in node.targets)]
    if len(definitions) != 1:
        raise ValueError('Profile must contain one literal GAME assignment')
    expected = ast.literal_eval(definitions[0])
    if not isinstance(expected, dict):
        raise ValueError('GAME profile must be a dictionary')
    validate_profile(expected)
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, required=True, help='Local raw Nintendo RomFS image')
    parser.add_argument('--out', type=Path, required=True, help='New packed output directory')
    parser.add_argument('--game-profile-source', type=Path, required=True,
                        help='Existing pinned 1.4.3 Python source containing literal GAME')
    parser.add_argument('--index-script', type=Path, required=True,
                        help='Existing trusted local make_romfs_index.py (executed with this Python)')
    args = parser.parse_args(argv)
    expected = load_profile(args.game_profile_source)
    # Estimate from the profile byte floor plus alignment, excluding small indexes.
    print(json.dumps({'estimated_packed_bytes':
                      expected['romfs_bytes'] + 15 * expected['romfs_files'],
                      'output': str(args.out)}), flush=True)
    print(json.dumps(pack(args.romfs, args.out, expected, args.index_script),
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
