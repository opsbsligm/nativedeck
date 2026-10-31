"""Build authored controller art and independently decode the embedded bitmaps.

No game assets, GPU, network or system configuration are used by these checks.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PORT = Path(__file__).resolve().parents[2]/'ports/ultratears-linux'
ART = PORT/'controller-art'


class ControllerArtwork(unittest.TestCase):
    def test_renderer_boundaries_and_embedded_art_match_native_render(self):
        compiler = shutil.which('cc') or shutil.which('clang')
        self.assertIsNotNone(compiler, 'A native C compiler is required')
        with tempfile.TemporaryDirectory(prefix='controller-art-check-', dir=ART) as name:
            scratch = Path(name)
            original = scratch/'original-check'
            self.run_checked([compiler, '-O2', '-std=c11', str(ART/'test_renderer.c'), '-lm', '-o', str(original)])
            self.run_checked([str(original), str(ART/'vendor/FiraSans-SemiBold.ttf')])
            source = scratch/'embedded-check.c'
            source.write_text(r'''
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "steamdeck_renderer.h"
#include "totk_deck_bitmaps.h"
int main(int argc, char **argv) {
    if (argc!=2) return 2;
    char error[256];
    sd_renderer *renderer=sd_renderer_create(argv[1],error,sizeof error);
    if (!renderer) { fprintf(stderr,"%s\n",error); return 3; }
    uint8_t *drawn=malloc(ND_DECK_BYTES), *decoded=malloc(ND_DECK_BYTES+8);
    if (!drawn || !decoded) return 4;
    memset(decoded,0x5a,ND_DECK_BYTES+8);
    if (nd_deck_unpack(0,decoded,ND_DECK_BYTES)!=-1 ||
        nd_deck_unpack(1,decoded,ND_DECK_BYTES-1)!=-1) return 5;
    for (size_t i=0;i<ND_DECK_BYTES+8;i++) if (decoded[i]!=0x5a) return 6;
    if (nd_deck_source_view("0000000000000000000000000000000000000000000000000000000000000000")) return 7;
    for (int view=1;view<=2;view++) {
        int rc=view==1 ? sd_render_front(renderer,drawn,ND_DECK_BYTES,580*4) :
                         sd_render_inclined(renderer,drawn,ND_DECK_BYTES,580*4);
        if (rc || nd_deck_unpack(view,decoded,ND_DECK_BYTES) || memcmp(drawn,decoded,ND_DECK_BYTES)) return 8;
        for (size_t i=ND_DECK_BYTES;i<ND_DECK_BYTES+8;i++) if (decoded[i]!=0x5a) return 9;
    }
    free(drawn); free(decoded); sd_renderer_destroy(renderer); return 0;
}
''')
            binary = scratch/'embedded-check'
            self.run_checked([compiler, '-O2', '-std=c11', '-I'+str(ART), '-I'+str(PORT/'controller-runtime'),
                              str(source), str(ART/'steamdeck_renderer.c'), '-lm', '-o', str(binary)])
            self.run_checked([str(binary), str(ART/'vendor/FiraSans-SemiBold.ttf')])

    def run_checked(self, args):
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
