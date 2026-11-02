#!/usr/bin/env python3
"""Retarget verified single-button tutorial states to the authored Deck image.

Consumes private, user-provided BFLYT/BFLAN files; never includes game resources.
Only seven known states of each of the three patterns are in scope. Other
tutorials, ali1 runtime behavior, and physical input need separate verification.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import resource_layout as P
from anchor_contract import validate as validate_anchors
from build_controller_patch import blob, invpoint, tag_bytes, world, synthetic

LAYOUT = 'blyt/PaActionGuide_00.bflyt'
CHILD = 'blyt/PaController_00.bflyt'
STATES = {0: 'face_west', 3: 'menu', 4: 'view', 11: 'menu',
          14: 'view', 19: 'left_stick', 23: 'face_west'}
ROOT = 'N_Guide1L_00'
ALIGN = 'A_Guide1LAlign_00'
LINE = 'W_Guide1Line_00'
MARKER = 'P_Guide1LCircle_00'
FIELDS = {ROOT: ('translation_x', 'translation_y'),
          ALIGN: ('rotation_z',), LINE: ('width', 'translation_x')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_inputs(root):
    names = [LAYOUT, CHILD] + [f'anim/PaActionGuide_00_Pattern{k}.bflan'
                              for k in 'ABC']
    result = {}
    for name in names:
        path = (root / name).resolve()
        assert path.is_relative_to(root) and path.is_file(), name
        result[name] = path.read_bytes()
    return result


def curve(prop, values):
    keys = [(0., values[0])]
    for f in range(1, len(values)):
        keys.extend(((float(f), values[f - 1]), (float(f), values[f])))
    return struct.pack('<BBHHHI', 0, P.PROPS.index(prop), 2, len(keys), 0, 12) + b''.join(
        struct.pack('<fff', frame, value, 0.) for frame, value in keys)


def held_only(channel):
    assert channel['data_type'] == 2
    for a, b in zip(channel['keys'], channel['keys'][1:]):
        if a['frame'] != b['frame']:
            assert a['value'] == b['value'] and a['slope'] == b['slope'] == 0, (
                'Interpolated source channel is outside this patch contract', channel['property'])


def rebuild(raw, entry, solutions):
    start = entry['offset']
    count = raw[start + 28]
    fields = FIELDS[entry['name']]
    blocks, seen = [], set()
    for j in range(count):
        at = start + struct.unpack_from('<I', raw, start + 32 + j * 4)[0]
        tag = raw[at:at + 4].decode('ascii')
        channels = [c for c in entry['channels'] if c['tag'] == tag]
        assert len(channels) == raw[at + 4]
        data = []
        for c in channels:
            if tag == 'FLPA' and c['property'] in fields:
                held_only(c)
                data.append(curve(c['property'], [s[entry['name']][c['property']]
                                                  for s in solutions]))
                seen.add(c['property'])
            else:
                data.append(blob(raw, c))
        if tag == 'FLPA':
            for prop in fields:
                if prop not in seen:
                    data.append(curve(prop, [s[entry['name']][prop] for s in solutions]))
                    seen.add(prop)
        blocks.append(tag_bytes(tag, data, raw[at:at + 8]))
    assert seen == set(fields)
    out = bytearray(raw[start:start + 32]) + bytearray(4 * count)
    for j, block in enumerate(blocks):
        struct.pack_into('<I', out, 32 + j * 4, len(out))
        out.extend(block)
    return bytes(out)


def patch_animation(raw, parsed, solutions):
    section = next(s for s in parsed['sections'] if s['tag'] == 'pai1')
    at, size = section['offset'], section['size']
    payload = bytearray(raw[at:at + size])
    offsets = []
    for entry in parsed['entries']:
        if entry['name'] in FIELDS:
            assert entry['target_type'] == 0
            offsets.append(len(payload))
            payload.extend(rebuild(raw, entry, solutions))
        else:
            offsets.append(entry['offset'] - at)
    table = len(payload)
    payload.extend(b''.join(struct.pack('<I', value) for value in offsets))
    struct.pack_into('<I', payload, 16, table)
    struct.pack_into('<I', payload, 4, len(payload))
    out = bytearray(raw[:at]) + payload + raw[at + size:]
    struct.pack_into('<I', out, 12, len(out))
    return bytes(out)


def solve(layout, child, animation, anchors, document):
    pm = {p['name']: p for p in layout['panes']}
    cm = next(p for p in child['panes'] if p['name'] == 'P_Controller_00')
    cg = P.geometry(child)[cm['id']]
    assert cm['origin_flags'] == 0
    solutions, records = [], []
    for frame in range(animation['frame_size'] + 1):
        g = P.geometry(layout, animation, frame)
        fields = {n: {key: g[pm[n]['id']]['values'][key] for key in keys}
                  for n, keys in FIELDS.items()}
        if frame in STATES:
            root, align, line, marker = [pm[n] for n in (ROOT, ALIGN, LINE, MARKER)]
            assert root['origin_flags'] == align['origin_flags'] == line['origin_flags'] == 0
            assert align['values']['translation_x'] == align['values']['translation_y'] == 0
            assert line['values']['translation_y'] == 0
            part = pm['Pa_Controller_00']
            sx, sy = part['parts_scale']
            picture = P.mul(P.mul(g[part['id']]['matrix'], [[sx, 0, 0], [0, sy, 0], [0, 0, 1]]), cg['matrix'])
            px, py = anchors[STATES[frame]]['pixel']
            target = world(picture, [(-.5 + px / document['width']) * cm['values']['width'],
                                     (.5 - py / document['height']) * cm['values']['height']])
            old_marker = g[marker['id']]['center']
            label_end = g[line['id']]['centerline_horizontal'][1]
            gap = math.dist(old_marker, g[line['id']]['centerline_horizontal'][0])
            parent = g[root['parent']]['matrix']
            old_local, new_local = invpoint(parent, old_marker), invpoint(parent, target)
            fields[ROOT]['translation_x'] += new_local[0] - old_local[0]
            fields[ROOT]['translation_y'] += new_local[1] - old_local[1]
            merged = {x['name']: {k: g[x['id']]['values'][k] for k in P.PROPS}
                      for x in layout['panes']}
            for name, changes in fields.items():
                merged[name].update(changes)
            moved = P.geometry(layout, synthetic(merged))
            parent_matrix = moved[align['parent']]['matrix']
            origin = moved[align['id']]['origin']
            local_target, local_end = invpoint(parent_matrix, origin), invpoint(parent_matrix, label_end)
            dx, dy = local_end[0] - local_target[0], local_end[1] - local_target[1]
            scale_x, scale_y = g[align['id']]['values']['scale_x'], g[align['id']]['values']['scale_y']
            assert scale_x == scale_y == 1 and g[root['id']]['values']['scale_x'] == 1
            length = math.hypot(dx, dy)
            assert length > gap + 4
            fields[ALIGN]['rotation_z'] = math.degrees(math.atan2(dy, dx))
            fields[LINE].update(width=length - gap, translation_x=(length + gap) / 2)
            records.append({'frame': frame, 'anchor_id': STATES[frame],
                            'target_layout': target, 'preserved_label_end': label_end,
                            'original_marker': old_marker})
        solutions.append(fields)
    return solutions, records


def verify(before, after, layout, records):
    old = P.parse_animation(before)
    new = P.parse_animation(after)
    assert old['frame_size'] == new['frame_size'] == 32
    assert old['textures'] == new['textures'] and old['pattern'] == new['pattern']
    old_entries = {(e['target_type'], e['name']): e for e in old['entries']}
    new_entries = {(e['target_type'], e['name']): e for e in new['entries']}
    assert old_entries.keys() == new_entries.keys()
    for key, entry in old_entries.items():
        updated = new_entries[key]
        channels = {(c['tag'], c['index'], c['target']): c for c in updated['channels']}
        for c in entry['channels']:
            ckey = (c['tag'], c['index'], c['target'])
            if key[0] != 0 or key[1] not in FIELDS or c['tag'] != 'FLPA' or c['property'] not in FIELDS[key[1]]:
                assert blob(before, c) == blob(after, channels[ckey]), ('Unexpected channel change', key, ckey)
    pm = {p['name']: p for p in layout['panes']}
    max_marker = max_label = 0.
    for record in records:
        g = P.geometry(layout, new, record['frame'])
        max_marker = max(max_marker, math.dist(g[pm[MARKER]['id']]['center'], record['target_layout']))
        max_label = max(max_label, math.dist(g[pm[LINE]['id']]['centerline_horizontal'][1], record['preserved_label_end']))
    assert max_marker < .001 and max_label < .001
    for frame in range(33):
        if frame in STATES:
            continue
        for fraction in (0., .25, .5, .75):
            if frame == 32 and fraction:
                continue
            g0, g1 = P.geometry(layout, old, frame + fraction), P.geometry(layout, new, frame + fraction)
            for a, b in zip(g0, g1):
                assert math.dist(a['origin'], b['origin']) < .001 and math.dist(a['center'], b['center']) < .001
                for prop in P.PROPS:
                    assert abs(a['values'][prop] - b['values'][prop]) < .001, (frame, a['name'], prop)
    return {'max_marker_error_layout': max_marker, 'max_label_end_drift_layout': max_label,
            'all_non_target_channels_byte_exact': True, 'other_states_geometry_preserved': True}


def build(root, anchor_path, output):
    if not __debug__:
        raise RuntimeError('Do not use Python -O')
    root, output = root.resolve(), output.resolve()
    assert not output.exists() and not output.is_relative_to(root)
    originals = read_inputs(root)
    document = json.loads(anchor_path.read_bytes())
    anchors = validate_anchors(document)
    assert all(x in anchors for x in STATES.values())
    layout, child = P.parse_layout(originals[LAYOUT]), P.parse_layout(originals[CHILD])
    patches, records = {}, {}
    for kind in 'ABC':
        name = f'anim/PaActionGuide_00_Pattern{kind}.bflan'
        parsed = P.parse_animation(originals[name])
        assert parsed['frame_size'] == 32
        solutions, expected = solve(layout, child, parsed, anchors, document)
        patched = patch_animation(originals[name], parsed, solutions)
        result = verify(originals[name], patched, layout, expected)
        patches[name] = patched
        records[kind] = {'expected': expected, 'verification': result}
    manifest = {'schema': 1, 'scope': 'seven-single-control-action-guide-states-per-pattern',
                'states': STATES, 'patterns': records, 'files': [],
                'anchor_sha256': sha(anchor_path.read_bytes()),
                'all_tutorials_validated': False, 'hardware_validated': False,
                'caveat': 'Stored transforms only; runtime ali1 alignment and inputs need actual game acceptance'}
    output.mkdir(parents=True)
    for name, data in patches.items():
        path = output / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        assert path.read_bytes() == data and (root / name).read_bytes() == originals[name]
        manifest['files'].append({'name': name, 'original_sha256': sha(originals[name]),
                                  'sha256': sha(data), 'bytes': len(data)})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--anchors', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.input_root, args.anchors, args.output)
    print(json.dumps({'states': len(STATES), 'patterns': len(result['patterns']),
                      'output': str(args.output), 'hardware_validated': False}))


if __name__ == '__main__':
    main()
