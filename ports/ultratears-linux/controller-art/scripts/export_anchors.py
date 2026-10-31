"""Export/check combined and per-view anchors from the C renderer's own arrays."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def documents():
    combined = json.loads(subprocess.check_output([str(ROOT/'build/render_deck'), '--anchors']))
    result = {'anchors.json': combined}
    for view in ('front', 'inclined'):
        transform = {'translation': combined['front_offset']} if view == 'front' else combined['inclined_projection']
        result[f'anchors-{view}.json'] = {
            'schema': 2, 'view': view,
            'coordinate_system': combined['coordinate_system'],
            'pixel_format': combined['pixel_format'],
            'game_layout_validated': False,
            'source_canvas': combined['front_source'], 'transform': transform,
            'resources': [name for name, target in combined['resource_mapping'].items() if target == view],
            **combined[view],
        }
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true', help='compare without writing')
    args = p.parse_args()
    for name, doc in documents().items():
        if args.check:
            assert json.loads((ROOT/name).read_text()) == doc, f'{name} differs from C arrays'
        else:
            (ROOT/name).write_text(json.dumps(doc, indent=2)+'\n')
        print(f'{name}: '+('matches C arrays' if args.check else 'exported'))

if __name__ == '__main__':
    main()
