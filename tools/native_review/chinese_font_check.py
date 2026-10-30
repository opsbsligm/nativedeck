"""Read-only TrueType and BOTW Chinese message coverage checks. No game data is written."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def unpack(data):
    if data[:4] != b'Yaz0':
        return data
    size = int.from_bytes(data[4:8], 'big')
    if size > 128 * 1024**2:
        raise ValueError('Unexpected archive size')
    out, at = bytearray(), 16
    while len(out) < size:
        code = data[at]
        at += 1
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if code & (1 << bit):
                out.append(data[at]); at += 1
            else:
                a, b = data[at:at+2]; at += 2
                length = a >> 4
                if length:
                    length += 2
                else:
                    length = data[at] + 18; at += 1
                distance = ((a & 15) << 8) + b + 1
                if distance > len(out) or len(out) + length > size:
                    raise ValueError('Invalid Yaz0 reference')
                for _ in range(length):
                    out.append(out[-distance])
    return bytes(out)


def archive(data):
    data = unpack(data)
    if data[:4] != b'SARC':
        raise ValueError('Expected SARC')
    endian = '<' if data[6:8] == b'\xff\xfe' else '>'
    header = struct.unpack_from(endian+'H', data, 4)[0]
    start = struct.unpack_from(endian+'I', data, 12)[0]
    if data[header:header+4] != b'SFAT':
        raise ValueError('Missing SFAT')
    count = struct.unpack_from(endian+'H', data, header+6)[0]
    nodes, names = header+12, header+12+16*count+8
    for i in range(count):
        _, attr, lo, hi = struct.unpack_from(endian+'4I', data, nodes+16*i)
        at = names + (attr & 0xffffff)*4
        if lo > hi or start+hi > len(data):
            raise ValueError('SARC entry out of bounds')
        name = data[at:data.index(0, at)].decode()
        yield name, data[start+lo:start+hi]


def font_characters(path):
    data = path.read_bytes()
    face = struct.unpack_from('>I', data, 12)[0] if data[:4] == b'ttcf' else 0
    if data[face:face+4] != b'\0\1\0\0':
        raise ValueError('Expected TrueType with glyf outlines')
    count = struct.unpack_from('>H', data, face+4)[0]
    tables = {data[face+12+i*16:face+16+i*16].decode(): struct.unpack_from('>II', data, face+20+i*16)
              for i in range(count)}
    if 'glyf' not in tables or 'CFF ' in tables:
        raise ValueError('Game font engine requires TrueType glyf outlines')
    cmap, length = tables['cmap']
    result = set()
    for i in range(struct.unpack_from('>H', data, cmap+2)[0]):
        platform, _, relative = struct.unpack_from('>HHI', data, cmap+4+i*8)
        if platform not in (0, 3):
            continue
        q = cmap+relative
        fmt = struct.unpack_from('>H', data, q)[0]
        if fmt == 12:
            for j in range(struct.unpack_from('>I', data, q+12)[0]):
                lo, hi, glyph = struct.unpack_from('>III', data, q+16+j*12)
                if hi > 0x10ffff or hi < lo:
                    raise ValueError('Invalid Unicode range')
                result.update(range(lo+(glyph == 0), hi+1))
        elif fmt == 4:
            n = struct.unpack_from('>H', data, q+6)[0]//2
            ends, starts = q+14, q+16+2*n
            deltas, offsets = starts+2*n, starts+4*n
            for j in range(n):
                lo = struct.unpack_from('>H', data, starts+2*j)[0]
                hi = struct.unpack_from('>H', data, ends+2*j)[0]
                delta = struct.unpack_from('>h', data, deltas+2*j)[0]
                offset = struct.unpack_from('>H', data, offsets+2*j)[0]
                for cp in range(lo, min(hi, 65534)+1):
                    glyph = struct.unpack_from('>H', data, offsets+2*j+offset+2*(cp-lo))[0] if offset else cp
                    if glyph and ((glyph+delta) & 65535):
                        result.add(cp)
    return result, hashlib.sha256(data).hexdigest()


def chinese_text(data):
    if data[:8] != b'MsgStdBn':
        return set()
    endian = '<' if data[8:10] == b'\xff\xfe' else '>'
    at, found = 0x20, set()
    while at+16 <= len(data):
        tag, size = data[at:at+4], struct.unpack_from(endian+'I', data, at+4)[0]
        body = data[at+16:at+16+size]
        if len(body) != size:
            raise ValueError('MSBT section out of bounds')
        if tag == b'TXT2':
            count = struct.unpack_from(endian+'I', body)[0]
            for i in range(count):
                pos = struct.unpack_from(endian+'I', body, 4+4*i)[0]
                while pos+2 <= len(body):
                    cp = struct.unpack_from(endian+'H', body, pos)[0]; pos += 2
                    if cp == 0:
                        break
                    if cp == 14:
                        n = struct.unpack_from(endian+'H', body, pos+4)[0]
                        pos += 6+n
                    elif cp == 15:
                        pos += 4
                    elif 0x3400 <= cp <= 0x9fff:
                        found.add(cp)
        at = (at+16+size+15) & ~15
    return found


def inspect(font, bootup):
    covered, sha = font_characters(font)
    chars, messages = set(), 0
    for name, payload in archive(bootup.read_bytes()):
        if 'Msg_CNzh' in name:
            for message, data in archive(payload):
                if data[:8] == b'MsgStdBn':
                    chars.update(chinese_text(data)); messages += 1
    if not messages or len(chars) < 100:
        raise ValueError('Chinese message archive not found or incomplete scan')
    missing = sorted(chars-covered)
    return {'font_sha256': sha, 'true_type_glyf': True, 'message_files': messages,
            'required_cjk_characters': len(chars), 'missing_cjk_characters': missing,
            'coverage_passed': not missing, 'rendered_chinese_validated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('font', type=Path)
    parser.add_argument('bootup', type=Path)
    args = parser.parse_args()
    result = inspect(args.font, args.bootup)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['coverage_passed'] else 1)
