"""Apply Chinese language selection and Deck defaults to the public 1.0.0 runtime."""
import argparse
import hashlib
import json
from pathlib import Path


PROFILE = Path(__file__).resolve().parents[2]/'ports/totk-recomp-linux/deck_language.h'
OLD_LANGUAGE = '    u64 v = 0; memcpy(&v, "en-US", 5); c->x[0] = v;'
NEW_LANGUAGE = '    c->x[0] = deck_desired_language();'
OLD_FPS = 'export TOTK_FPS="${TOTK_FPS:-90}"'
NEW_DEFAULTS = '''export TOTK_FPS="${TOTK_FPS:-30}"
export TOTK_LANG="${TOTK_LANG:-zh-Hans}"
# Xbox glyphs describe physical positions, including inherited environments.
unset TOTK_PAD_LABELS'''


def apply(source):
    source = Path(source)
    language = source/'runtime/hle_oe.cpp'
    launcher = source/'tools/linux/run.sh'
    header = source/'runtime/deck_language.h'
    old_language, old_launcher = language.read_text(), launcher.read_text()
    supplied = PROFILE.read_bytes()
    if NEW_LANGUAGE in old_language:
        if (header.read_bytes() != supplied or NEW_DEFAULTS not in old_launcher or
                '#include "deck_language.h"' not in old_language):
            raise ValueError('Existing Deck profile differs; preserve it')
        return {'already_applied': True}
    if (old_language.count(OLD_LANGUAGE) != 1 or
            old_language.count('#include "hle.h"') != 1 or
            old_launcher.count(OLD_FPS) != 1 or header.exists()):
        raise ValueError('Unsupported runtime or launcher; no changes')
    updated = old_language.replace('#include "hle.h"', '#include "hle.h"\n#include "deck_language.h"', 1)
    updated = updated.replace(OLD_LANGUAGE, NEW_LANGUAGE, 1)
    updated = updated.replace('language en-US,', 'language selected by TOTK_LANG,', 1)
    new_launcher = old_launcher.replace(OLD_FPS, NEW_DEFAULTS, 1)
    new_launcher = new_launcher.replace('TOTK_FPS=90 (default: the OLED panel\'s 90 Hz)', 'TOTK_FPS=30 (Deck default)', 1)
    header.write_bytes(supplied)
    language.write_text(updated)
    launcher.write_text(new_launcher)
    return {'already_applied': False, 'default_language': 'zh-Hans', 'default_fps': 30,
            'pad_mapping': 'position', 'hardware_validated': False,
            'files': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (header, language, launcher)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.source), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc)+'\n')
