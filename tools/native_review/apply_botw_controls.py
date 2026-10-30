"""Make configuration's controller labels follow the explicitly selected icon family."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path


def apply(source):
    target=Path(source)/'runtime/hle/bindings.c'
    old=target.read_text()
    marker='// Explicit prompt selection also names the physical buttons in Controls.'
    if marker in old:
        return {'already_applied':True,'sha256':hashlib.sha256(old.encode()).hexdigest()}
    anchor='int bind_label_family(void) {'
    if old.count(anchor)!=1 or old.count('#include "../hle.h"')!=1:
        raise ValueError('Unsupported bindings source; no changes')
    new=old.replace('#include "../hle.h"','#include "../hle.h"\n#include "../settings.h"',1)
    new=new.replace(anchor,anchor+'''
    // Explicit prompt selection also names the physical buttons in Controls.
    switch (g_settings.button_icons) {
    case ICONS_XBOX: return 1;
    case ICONS_PLAYSTATION: return 2;
    case ICONS_NINTENDO: return 0;
    default: break;
    }
''',1)
    target.write_text(new)
    patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
                                     fromfile='a/runtime/hle/bindings.c',tofile='b/runtime/hle/bindings.c'))
    return {'already_applied':False,'sha256':hashlib.sha256(new.encode()).hexdigest(),'patch':patch}


def apply_diagram(source):
    root=Path(source)
    path=root/'runtime/nvn/glyphs.c'
    textures=root/'runtime/nvn/vulkan/textures.c'
    code=Path(__file__).with_name('botw_xbox_diagram.inc').read_text()
    destination=root/'runtime/nvn/deck_xbox_diagram.inc'
    a,b=path.read_text(),textures.read_text()
    anchor='bool glyphs_apply_layout(uint32_t format, uint32_t w, uint32_t h, uint8_t *lin, uint32_t row) {'
    hook='if (lv == 0 && layer == 0 && t->format == 0x01 && !linear &&'
    if '#include "deck_xbox_diagram.inc"' in a:
        if destination.read_text()!=code or 'if (deck_xbox_diagram(format, w, h, lin, row)) return true;' not in a or \
                '(t->format == 0x01 || t->format == 0x0d)' not in b:
            raise ValueError('Existing diagram patch differs; preserve it')
        return {'already_applied':True}
    if a.count(anchor)!=1 or b.count(hook)!=1 or destination.exists():
        raise ValueError('Unsupported texture hook; no changes')
    a=a.replace(anchor,'#include "deck_xbox_diagram.inc"\n\n'+anchor+'\n    if (deck_xbox_diagram(format, w, h, lin, row)) return true;',1)
    b=b.replace(hook,'if (lv == 0 && layer == 0 && (t->format == 0x01 || t->format == 0x0d) && !linear &&',1)
    destination.write_text(code)
    path.write_text(a);textures.write_text(b)
    return {'already_applied':False,'sha256':hashlib.sha256(code.encode()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--patch',type=Path)
    parser.add_argument('--diagram',action='store_true')
    args=parser.parse_args()
    result=apply(args.source)
    if args.diagram:
        result['diagram']=apply_diagram(args.source)
    patch=result.pop('patch',None)
    if args.patch and patch:
        with args.patch.open('x') as stream:stream.write(patch)
    print(json.dumps(result))
