"""Replace literal Switch letters in the 1.4.3 contextual action layout.

The active buttons are separate icon textures. These plain UTF-16 letters label
the three inactive positions, including the companion variant of the A prompt.
Only sixteen existing UTF-16 code units change; no geometry or event IDs change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

LABELS = {
    'T_B_00': ('B', 'A'), 'T_X_00': ('X', 'Y'), 'T_Y_00': ('Y', 'X'),
    'T_B_01': ('B', 'A'), 'T_X_02': ('X', 'Y'), 'T_Y_03': ('Y', 'X'),
    'T_A_01': ('A', 'B'), 'T_X_01': ('X', 'Y'), 'T_Y_01': ('Y', 'X'),
    'T_A_02': ('A', 'B'), 'T_B_02': ('B', 'A'), 'T_Y_02': ('Y', 'X'),
    'T_A_03': ('A', 'B'), 'T_B_03': ('B', 'A'), 'T_X_03': ('X', 'Y'),
    'T_Plus_00': ('+', '\ue04b'),
}
MEMBER = 'blyt/DoCommand_00.bflyt'
LAYOUT = 'UI/LayoutArchive/Common.Product.140.Nin_NX_NVN.blarc.zs'


def patch_layout(blob):
    if (len(blob) < 20 or blob[:6] != b'FLYT\xff\xfe'
            or struct.unpack_from('<I', blob, 8)[0] != 0x09000000
            or struct.unpack_from('<I', blob, 12)[0] != len(blob)):
        raise ValueError('Expected complete little-endian FLYT version 9')
    pos = struct.unpack_from('<H', blob, 6)[0]
    count = struct.unpack_from('<H', blob, 16)[0]
    if not 20 <= pos <= len(blob):
        raise ValueError('Invalid FLYT section start')
    output = bytearray(blob)
    changes = []
    found = set()
    for _ in range(count):
        if pos+8 > len(blob):
            raise ValueError('Truncated FLYT section')
        size = struct.unpack_from('<I', blob, pos+4)[0]
        end = pos+size
        if size < 8 or size % 4 or end > len(blob):
            raise ValueError('Invalid FLYT section extent')
        if blob[pos:pos+4] == b'txt1':
            if size < 136:
                raise ValueError('Truncated text pane')
            name = blob[pos+12:pos+44].split(b'\0', 1)[0].decode('ascii')
            if name in LABELS:
                if name in found:
                    raise ValueError('Duplicate contextual button pane: '+name)
                before, after = LABELS[name]
                at = pos+struct.unpack_from('<I', blob, pos+100)[0]
                # The character and terminator must both be inside this pane.
                if (at < pos+136 or at+4 > end
                        or blob[at:at+4] != before.encode('utf-16le')+b'\0\0'):
                    raise ValueError('Unexpected original contextual label: '+name)
                output[at:at+2] = after.encode('utf-16le')
                changes.append({'pane': name, 'offset': at, 'before': before, 'after': after})
                found.add(name)
        pos = end
    if pos != len(blob) or found != set(LABELS):
        raise ValueError('Contextual button layout is incomplete or has trailing bytes')
    return bytes(output), {'code_units_changed': len(changes), 'changes': changes,
        'before_sha256': hashlib.sha256(blob).hexdigest(),
        'after_sha256': hashlib.sha256(output).hexdigest(), 'geometry_changed': False}


def patch_archive(archive, members):
    if MEMBER not in members:
        raise ValueError('Contextual button layout is absent')
    lo, hi = members[MEMBER]
    if not 0 <= lo < hi <= len(archive):
        raise ValueError('Invalid contextual layout member extent')
    replacement, proof = patch_layout(archive[lo:hi])
    result = archive[:lo]+replacement+archive[hi:]
    if len(result) != len(archive):
        raise ValueError('Context label patch changed archive size')
    return result, proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('romfs', 'stage', 'tools'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    from ultratears_xbox import check_tools, regular_inside
    check_tools(args.tools)
    sys.path.insert(0, str(args.tools))
    from compression import zstd
    import make_button_icons as m
    index = m.read_index(regular_inside(args.romfs, 'runtime-index.bin'))
    offset, size = index['Pack/ZsDic.pack.zs']
    if not 0 < size <= 64*1024**2 or offset < 0:
        raise ValueError('Invalid dictionary pack size')
    with regular_inside(args.romfs, 'romfs.bin').open('rb') as stream:
        stream.seek(offset); packed = stream.read(size)
    if len(packed) != size:
        raise ValueError('Truncated dictionary pack')
    dictionaries = {}
    pack = zstd.decompress(packed)
    for lo, hi in m.sarc_members(pack).values():
        d = zstd.ZstdDict(pack[lo:hi]); dictionaries[d.dict_id] = d
    target = regular_inside(args.stage, LAYOUT)
    raw = target.read_bytes(); info = zstd.get_frame_info(raw)
    if not 0 < info.decompressed_size <= 256*1024**2:
        raise ValueError('Invalid layout archive size')
    dictionary = dictionaries[info.dictionary_id]
    archive = zstd.decompress(raw, zstd_dict=dictionary)
    updated, proof = patch_archive(archive, m.sarc_members(archive))
    encoded = zstd.compress(updated, level=19, zstd_dict=dictionary)
    if zstd.decompress(encoded, zstd_dict=dictionary) != updated:
        raise ValueError('Contextual UI compression roundtrip failed')
    target.write_bytes(encoded)
    m.make_mod_manifest.IMAGE_DIR = args.romfs
    m.write_mod_manifest(args.stage, args.romfs, index)
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
