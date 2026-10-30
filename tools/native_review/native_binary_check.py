"""Inspect native ELF output and reject empty TOTK runtime probes without executing them.

A nonempty table passes only this negative check. It never proves playability or
resource integrity; these require separate, matching hardware evidence.
"""
import argparse
import json
import mmap
import struct
from pathlib import Path


class InvalidElf(ValueError):
    pass


def inspect(path, require_totk_table=False):
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        size = len(data)

        def read(fmt, at):
            n = struct.calcsize(fmt)
            if at < 0 or at+n > size:
                raise InvalidElf('ELF structure outside file')
            return struct.unpack_from(fmt, data, at)

        if size < 64 or data[:6] != b'\x7fELF\x02\x01':
            raise InvalidElf('Expected little-endian ELF64')
        typ, machine = read('<HH', 16)
        if typ not in (2, 3) or machine != 62:
            raise InvalidElf('Expected x86-64 executable or shared object')
        phoff, shoff = read('<QQ', 32)
        phsize, phnum, shsize, shnum = read('<HHHH', 54)
        if phsize < 56 or shsize < 64 or not shnum:
            raise InvalidElf('Missing program or symbol metadata')
        sections = [read('<IIQQQQIIQQ', shoff+i*shsize) for i in range(shnum)]
        segments = [read('<IIQQQQQQ', phoff+i*phsize) for i in range(phnum)]
        counters = {}
        for sec in sections:
            if sec[1] not in (2, 11):  # SYMTAB or DYNSYM
                continue
            if sec[6] >= shnum or sec[9] != 24 or sec[5] % 24:
                raise InvalidElf('Malformed ELF symbol table')
            names = sections[sec[6]]
            if names[4]+names[5] > size:
                raise InvalidElf('Malformed ELF string table')
            for at in range(sec[4], sec[4]+sec[5], 24):
                name, info, other, index, value, length = read('<IBBHQQ', at)
                if name >= names[5]:
                    raise InvalidElf('Symbol name outside string table')
                start = names[4]+name
                end = data.find(b'\0', start, names[4]+names[5])
                if end < 0:
                    raise InvalidElf('Unterminated symbol name')
                label = data[start:end].decode(errors='replace')
                if label not in ('g_ftab_count', 'g_s_ftab_count', 'g_imp_count') or not index:
                    continue
                if info & 15 != 1 or length != 8:
                    raise InvalidElf('Unexpected function table counter type')
                addresses = [p[2]+value-p[3] for p in segments
                             if p[0] == 1 and p[3] <= value and value+8 <= p[3]+p[5]]
                if len(addresses) != 1:
                    raise InvalidElf('Counter is not uniquely file-backed')
                count = read('<Q', addresses[0])[0]
                if label in counters and counters[label] != count:
                    raise InvalidElf('Contradicting counter symbols')
                counters[label] = count
        errors = []
        if require_totk_table:
            if 'g_ftab_count' not in counters:
                errors.append('game_function_table_not_proven')
            elif counters['g_ftab_count'] == 0:
                errors.append('empty_game_function_table_runtime_probe_only')
        return {'binary': str(path), 'elf64_x86_64': True, 'function_counters': counters,
                'inspection_passed': not errors, 'errors': errors,
                'playability_validated': False, 'release_accepted': False,
                'evidence_required': ['matching game version and input hashes',
                                      'complete and verified resources',
                                      'Steam entry launch, save/load and controls',
                                      'Chinese text and Xbox prompts on screen']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--totk', action='store_true')
    args = parser.parse_args()
    try:
        result = inspect(args.binary, args.totk)
    except (InvalidElf, OSError, ValueError) as exc:
        result = {'inspection_passed': False, 'release_accepted': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['inspection_passed'] else 1)
