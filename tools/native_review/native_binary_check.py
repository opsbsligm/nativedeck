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


def inspect(path, require_totk_table=False, require_ultratears=False):
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
        entry = read('<Q', 24)[0]
        interpreter = None
        for segment in segments:
            if segment[0] == 3:
                if interpreter is not None: raise InvalidElf('Multiple ELF interpreters')
                if segment[5] < 2 or segment[5] > 4096 or segment[2]+segment[5] > size:
                    raise InvalidElf('Invalid native interpreter')
                raw = data[segment[2]:segment[2]+segment[5]]
                if not raw.endswith(b'\0') or b'\0' in raw[:-1]:
                    raise InvalidElf('Malformed interpreter name')
                interpreter = raw[:-1].decode('ascii')
        counters = {}
        symbols = {}
        modules = {'main': (0x0800000000, 0x0804000000),
                   'subsdk0': (0x0804000000, 0x0805000000),
                   'sdk': (0x0805000000, 0x0807000000)}
        table_names = {m+'_fn_'+f for m in modules for f in ('count','addrs','ptrs')}
        count_names = {'g_ftab_count','g_s_ftab_count','g_imp_count'} | {m+'_fn_count' for m in modules}

        def file_offset(value, length):
            offsets = [p[2]+value-p[3] for p in segments
                       if p[0] == 1 and p[3] <= value and value+length <= p[3]+p[5]]
            if len(offsets) != 1 or offsets[0]+length > size:
                raise InvalidElf('Symbol is not uniquely file-backed')
            return offsets[0]

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
                if label not in count_names | table_names or not index:
                    continue
                record = (value, length, info & 15)
                if label in symbols and symbols[label] != record:
                    raise InvalidElf('Contradicting symbol definitions')
                symbols[label] = record
                if label not in count_names:
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
        if require_ultratears:
            if not entry or not any(p[0] == 1 and p[1] & 1 and p[3] <= entry < p[3]+p[5] for p in segments):
                errors.append('native_executable_entry_not_proven')
            if not interpreter or not interpreter.startswith('/') or Path(interpreter).name != 'ld-linux-x86-64.so.2':
                errors.append('native_glibc_interpreter_not_proven')
            for module, (lo, hi) in modules.items():
                count = counters.get(module+'_fn_count', 0)
                if not 0 < count <= 1000000:
                    errors.append(module+'_function_table_missing_or_empty')
                    continue
                arrays = []
                for suffix in ('addrs', 'ptrs'):
                    label = module+'_fn_'+suffix
                    item = symbols.get(label)
                    if not item or item[1:] != (count*8, 1):
                        errors.append(label+'_metadata_mismatch')
                        break
                    offset = file_offset(item[0], item[1])
                    arrays.append([x[0] for x in struct.iter_unpack('<Q',data[offset:offset+item[1]])])
                if len(arrays) != 2:
                    continue
                guest, native = arrays
                if guest != sorted(set(guest)) or any(a < lo or a >= hi or a % 4 for a in guest):
                    errors.append(module+'_guest_addresses_invalid')
                if any(not any(p[0] == 1 and p[1] & 1 and p[3] <= a < p[3]+p[5] for p in segments) for a in native):
                    errors.append(module+'_native_targets_invalid')
        if require_totk_table:
            if 'g_ftab_count' not in counters:
                errors.append('game_function_table_not_proven')
            elif counters['g_ftab_count'] == 0:
                errors.append('empty_game_function_table_runtime_probe_only')
        return {'binary': str(path), 'elf64_x86_64': True, 'elf_entry': entry, 'interpreter': interpreter, 'function_counters': counters,
                'inspection_passed': not errors, 'errors': errors,
                'playability_validated': False, 'release_accepted': False,
                'evidence_required': ['matching game version and input hashes',
                                      'complete and verified resources',
                                      'Steam entry launch, save/load and controls',
                                      'Chinese text and Xbox prompts on screen']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    profile = parser.add_mutually_exclusive_group()
    profile.add_argument('--totk', action='store_true')
    profile.add_argument('--ultratears', action='store_true')
    args = parser.parse_args()
    try:
        result = inspect(args.binary, args.totk, args.ultratears)
    except (InvalidElf, OSError, ValueError) as exc:
        result = {'inspection_passed': False, 'release_accepted': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['inspection_passed'] else 1)
