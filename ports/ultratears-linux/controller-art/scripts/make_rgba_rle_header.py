"""Pack authored 580x340 grayscale RGBA into the existing nd_deck_run C ABI.

Python stdlib only. No game texture input, decoder, font, network or game asset
access. Optional SHA/view metadata preserves an existing runtime whitelist.
See NOTICE.md and LICENSE.adaptation.txt. Output is deterministic UTF-8/LF.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

WIDTH, HEIGHT = 580, 340
PIXELS, BYTE_COUNT = WIDTH*HEIGHT, WIDTH*HEIGHT*4
FUNCTION = re.compile(r'static\s+inline\s+int\s+nd_deck_source_view\s*\(\s*const\s+char\s+sha\s*\[65\]\s*\)\s*\{([^{}]*)\}', re.S)
ENTRY = re.compile(r'if\s*\(\s*!strcmp\(sha,"([0-9a-f]{64})"\)\s*\)\s*return\s+([12]);')

def encode(raw):
    if len(raw) != BYTE_COUNT:
        raise ValueError(f'expected {BYTE_COUNT} RGBA bytes, got {len(raw)}')
    runs = []
    for at in range(0,len(raw),4):
        r,g,b,a = raw[at:at+4]
        if r != g or g != b:
            raise ValueError(f'non-grayscale pixel at {at//4}: existing ABI cannot encode RGB')
        if runs and runs[-1][1:] == (g,a) and runs[-1][0] < 65535:
            n,_,_ = runs[-1]; runs[-1] = (n+1,g,a)
        else:
            runs.append((1,g,a))
    if decode(runs) != raw:
        raise ValueError('internal RLE roundtrip mismatch')
    return runs

def decode(runs):
    total = 0
    for row in runs:
        if len(row)!=3 or any(type(n) is not int for n in row):
            raise ValueError('run must contain three integers')
        n,g,a = row
        if not 1<=n<=65535 or not 0<=g<=255 or not 0<=a<=255 or n>PIXELS-total:
            raise ValueError('invalid or overflowing run')
        total += n
    if total != PIXELS:
        raise ValueError('incomplete run stream')
    return b''.join(bytes((g,g,g,a))*n for n,g,a in runs)

def validate_views(rows):
    if not isinstance(rows,list) or len(rows)>128:
        raise ValueError('source views must be an array with at most 128 entries')
    out,seen = [],set()
    for row in rows:
        if not isinstance(row,dict): raise ValueError('invalid source view')
        sha,view = row.get('linear_sha256'),row.get('view')
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or type(view) is not int or view not in (1,2):
            raise ValueError('source view requires lowercase linear_sha256 and view 1 or 2')
        if sha in seen: raise ValueError('duplicate source SHA')
        seen.add(sha); out.append({'linear_sha256':sha,'view':view})
    return out

def views_from_header(text):
    matches = list(FUNCTION.finditer(text))
    if len(matches)!=1:
        raise ValueError('expected exactly one canonical nd_deck_source_view function')
    body = matches[0].group(1)
    rows = [{'linear_sha256':m[1],'view':int(m[2])} for m in ENTRY.finditer(body)]
    remainder = ENTRY.sub('',body)
    if not re.fullmatch(r'\s*return\s+0;\s*',remainder):
        raise ValueError('unrecognized source-view function; refusing to copy arbitrary C')
    return validate_views(rows)

def emit_header(bitmaps,views):
    views = validate_views(views)
    lines = ['/* Authored Steam Deck artwork only; no Nintendo pixels or game code. */',
             '/* Build-time Fira Sans OFL font and source notices accompany the renderer. */',
             '#ifndef ND_TOTK_DECK_BITMAPS_H','#define ND_TOTK_DECK_BITMAPS_H',
             '#include <stdint.h>','#include <stddef.h>','#include <string.h>',
             'enum { ND_DECK_W=580, ND_DECK_H=340, ND_DECK_BYTES=788800 };',
             'typedef struct { uint16_t n; uint8_t grey, alpha; } nd_deck_run;']
    records = {}
    for name in ('front','inclined'):
        raw = bitmaps[name]; runs = encode(raw)
        lines.append('static const nd_deck_run nd_deck_'+name+'[] = {')
        lines.extend('{%d,%d,%d},'%row for row in runs); lines.append('};')
        records[name] = {'rgba_sha256':hashlib.sha256(raw).hexdigest(),'runs':len(runs),'bytes':len(raw)}
    lines.append('static inline int nd_deck_source_view(const char sha[65]) {')
    lines.extend('    if (!strcmp(sha,"%s")) return %d;'%(row['linear_sha256'],row['view']) for row in views)
    lines += ['    return 0;','}',
              'static inline int nd_deck_unpack(int view, uint8_t *out, size_t bytes) {',
              '    if (!out || bytes < ND_DECK_BYTES || (view != 1 && view != 2)) return -1;',
              '    const nd_deck_run *runs = view == 1 ? nd_deck_front : nd_deck_inclined;',
              '    size_t count = view == 1 ? sizeof nd_deck_front/sizeof *runs : sizeof nd_deck_inclined/sizeof *runs;',
              '    size_t total=0;',
              '    for (size_t i=0;i<count;i++) {',
              '        if (!runs[i].n || runs[i].n > ND_DECK_W*ND_DECK_H-total) return -1;',
              '        total += runs[i].n;',
              '    }',
              '    if (total != ND_DECK_W*ND_DECK_H) return -1;',
              '    size_t at=0;',
              '    for (size_t i=0;i<count;i++) for (unsigned j=0;j<runs[i].n;j++) {',
              '        out[at++]=runs[i].grey; out[at++]=runs[i].grey;',
              '        out[at++]=runs[i].grey; out[at++]=runs[i].alpha;',
              '    }',
              '    return 0;','}','#endif']
    header = ('\n'.join(lines)+'\n').encode('utf-8')
    manifest = {'schema':1,'format':'nd-deck-run-v1','width':WIDTH,'height':HEIGHT,
                'authored_bitmaps':records,'target_identities':views,
                'header_sha256':hashlib.sha256(header).hexdigest(),
                'runtime_font_dependency':False,'game_asset_input':False,'hardware_validated':False}
    return header,manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graphics',type=Path,required=True,help='directory containing authored front.rgba/inclined.rgba')
    parser.add_argument('--out',type=Path,required=True,help='new output directory; existing directories are refused')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--source-views',type=Path,help='JSON array containing only linear_sha256/view metadata')
    group.add_argument('--source-views-from-header',type=Path,help='read only canonical source SHA/view function from an existing header')
    args = parser.parse_args()
    try:
        views = (validate_views(json.loads(args.source_views.read_text())) if args.source_views else
                 views_from_header(args.source_views_from_header.read_text()) if args.source_views_from_header else [])
        if args.out.exists(): raise ValueError('output directory already exists; retain prior artifacts')
        bitmaps = {name:(args.graphics/(name+'.rgba')).read_bytes() for name in ('front','inclined')}
        header,manifest = emit_header(bitmaps,views)
        args.out.mkdir(parents=True)
        (args.out/'totk_deck_bitmaps.h').write_bytes(header)
        (args.out/'steamdeck-bitmap-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps(manifest,indent=2))
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,str(error)+'\n')

if __name__=='__main__': main()
