"""Public offline RLE tests; only authored native-renderer pixels are used."""
from pathlib import Path
import json
import os
import shlex
import subprocess
import tempfile
import unittest
import make_rgba_rle_header as rle

ROOT = Path(__file__).resolve().parents[1]

class RLETests(unittest.TestCase):
    def test_run_splitting_and_roundtrip(self):
        raw=bytes((17,17,17,53))*rle.PIXELS
        runs=rle.encode(raw)
        self.assertEqual([r[0] for r in runs],[65535,65535,65535,595])
        self.assertEqual(rle.decode(runs),raw)

    def test_reject_invalid_pixels_and_runs(self):
        with self.assertRaises(ValueError): rle.encode(b'')
        with self.assertRaises(ValueError): rle.encode(bytes((1,2,3,255))*rle.PIXELS)
        for bad in ([],[(0,0,0)],[(65536,0,0)],[(1,256,0)],[(1,0,-1)],[(True,0,0)],[(1,0,0)]):
            with self.subTest(bad=bad),self.assertRaises(ValueError): rle.decode(bad)
        with self.assertRaises(ValueError): rle.decode([(65535,0,0)]*4)

    def test_reject_invalid_or_duplicate_identities(self):
        for rows in ([{'linear_sha256':'1'*64,'view':True}],
                     [{'linear_sha256':'bad','view':1}],
                     [{'linear_sha256':'1'*64,'view':1}]*2):
            with self.assertRaises(ValueError): rle.validate_views(rows)
        with self.assertRaises(ValueError):
            rle.views_from_header('static inline int nd_deck_source_view(const char sha[65]) { evil(); return 0; }')

    def test_native_art_header_determinism_cli_and_c_decoder(self):
        views=[{'linear_sha256':'1'*64,'view':1},{'linear_sha256':'2'*64,'view':2}]
        with tempfile.TemporaryDirectory(prefix='rle-test-',dir=ROOT/'build') as name:
            folder=Path(name); rawdir=folder/'raw'; rawdir.mkdir()
            for view in ('front','inclined'):
                subprocess.run([str(ROOT/'build/render_deck'),view,str(ROOT/'vendor/FiraSans-SemiBold.ttf'),str(rawdir/(view+'.rgba'))],check=True)
            images={view:(rawdir/(view+'.rgba')).read_bytes() for view in ('front','inclined')}
            header,manifest=rle.emit_header(images,views)
            self.assertEqual((header,manifest),rle.emit_header(images,views))
            self.assertEqual(rle.views_from_header(header.decode()),views)
            (folder/'views.json').write_text(json.dumps(views))
            cmd=['python3','-B',str(ROOT/'scripts/make_rgba_rle_header.py'),'--graphics',str(rawdir),'--source-views',str(folder/'views.json'),'--out',str(folder/'out')]
            subprocess.run(cmd,check=True,stdout=subprocess.PIPE)
            self.assertEqual((folder/'out/totk_deck_bitmaps.h').read_bytes(),header)
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual((folder/'out/totk_deck_bitmaps.h').read_bytes(),header)
            subprocess.run(shlex.split(os.environ.get('CC','cc'))+['-std=c11','-Wall','-Wextra','-Wpedantic','-Werror','-I'+str(folder/'out'),str(ROOT/'tests/test_rle_unpack.c'),'-o',str(folder/'unpack')],check=True)
            subprocess.run([str(folder/'unpack'),str(rawdir),'1'*64,'1','2'*64,'2'],check=True)
            # The generated format is also a standalone C++ header.
            (folder/'smoke.cpp').write_text('#include "totk_deck_bitmaps.h"\nstatic_assert(sizeof(nd_deck_run)==4,"ABI");\nint main(){return nd_deck_source_view("0000000000000000000000000000000000000000000000000000000000000000");}\n')
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+['-std=c++11','-Wall','-Wextra','-Werror','-I'+str(folder/'out'),str(folder/'smoke.cpp'),'-o',str(folder/'cpp')],check=True)
            subprocess.run([str(folder/'cpp')],check=True)

if __name__=='__main__': unittest.main(verbosity=2)
