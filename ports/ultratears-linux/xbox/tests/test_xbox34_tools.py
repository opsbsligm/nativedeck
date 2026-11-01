"""ROM-free offline tests for the PUBLIC prepare path and strict derivation."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import ultratears_xbox as ui
import xbox34_tools as tools

class Xbox34Tools(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='xbox34-',dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def derived(self):
        p=self.root/'derived';p.mkdir();meta=tools.derive_tools(tools.VENDOR,p,ui.check_tools);return p,meta
    def test_pristine_gate_and_derived_gate_are_distinct(self):
        ui.check_tools(tools.VENDOR);p,meta=self.derived()
        self.assertEqual(meta['glyph_count'],34)
        with self.assertRaisesRegex(ValueError,'pinned public'):ui.check_tools(p)
        self.assertEqual(tools.digest(p/'make_button_icons.py'),tools.pin()['after']['make_button_icons.py']['sha256'])
    def test_patch_tamper_and_source_context_mismatch_rejected(self):
        data=(tools.ROOT/'xbox-stick-icons-f1d00772.patch').read_text()
        source=(tools.VENDOR/'make_button_icons.py').read_text()
        with self.assertRaisesRegex(ValueError,'context mismatch'):
            tools.apply_patch_exact({'make_button_icons.py':source.replace('def xbox_style(g):','def xbox_style(zzz):')},data)
        with self.assertRaisesRegex(ValueError,'Unexpected patch path'):
            tools.apply_patch_exact({'make_button_icons.py':source},data.replace('b/test_xbox_sticks.py','b/../../bad.py'))
        with mock.patch.object(tools,'digest',side_effect=lambda p:'0'*64 if Path(p).name.endswith('.patch') else hashlib.sha256(Path(p).read_bytes()).hexdigest()):
            with self.assertRaisesRegex(ValueError,'patch SHA mismatch'):tools.pin()
    def test_after_sha_mismatch_rejected(self):
        info=tools.pin();info['after']['make_button_icons.py']['sha256']='0'*64
        with mock.patch.object(tools,'pin',return_value=info):
            with self.assertRaisesRegex(ValueError,'Derived tool SHA mismatch'):self.derived()
    def test_vendored_dependency_is_verified_and_available_without_site(self):
        env=dict(os.environ,PYTHONPATH=str(tools.fonttools_path()),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-S','-B','-c','import fontTools; from compression import zstd; print(fontTools.__version__); print(fontTools.__file__)'],env=env,text=True,capture_output=True,check=True)
        self.assertIn('4.68.0',result.stdout);self.assertIn('vendor/fonttools-4.68.0',result.stdout)
    def test_patched_synthetic_outlines_execute_offline_with_zero_skips(self):
        p,_=self.derived();env=dict(os.environ,PYTHONPATH=str(tools.fonttools_path()),PYTHONDONTWRITEBYTECODE='1')
        cmd='import unittest; s=unittest.defaultTestLoader.loadTestsFromName("test_xbox_sticks"); r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.testsRun==4 and r.wasSuccessful() and not r.skipped else 1)'
        result=subprocess.run([sys.executable,'-S','-B','-c',cmd],cwd=p,env=env,text=True,capture_output=True,check=True)
        self.assertIn('Ran 4 tests',result.stderr)
    def test_public_prepare_executes_derived_tools_and_records_provenance(self):
        import ultratears_bundle as bundle
        # Tiny bytes only. Mock the expensive MNG resource subprocess, not derivation,
        # source pin checks, dependency preflight or public manifest.
        # Linux uses its real no-replace publication; Mac gets a test-only rename shim.
        rom=self.root/'rom';rom.mkdir()
        (rom/'romfs.bin').write_bytes(b'synthetic')
        (rom/'runtime-index.bin').write_bytes(b'synthetic')
        (rom/'index.json').write_text(json.dumps({'status':'pass','content_sha256':'fixture','files':[]}))
        destination=self.root/'out';commands=[];realrun=subprocess.run
        def run(command,**kw):
            commands.append(command)
            if '-c' in command:return realrun(command,**kw)
            if Path(command[2]).name=='xbox_context_labels.py':
                self.assertEqual(Path(command[2]),Path(ui.__file__).with_name('xbox_context_labels.py'))
                args=dict(zip(command[3::2],command[4::2]))
                self.assertEqual(Path(args['--romfs']),rom)
                self.assertEqual(Path(args['--tools']),tools.VENDOR)
                stage=Path(args['--stage'])
                self.assertTrue((stage/'manifest.tsv').is_file())
                from xbox_context_labels import MESSAGES
                with (stage/'manifest.tsv').open('a') as f:
                    for name in sorted(MESSAGES):
                        p=stage/name;p.parent.mkdir(exist_ok=True);p.write_bytes(b'synthetic labels '+name.encode())
                        f.write('\t'.join((name,str(p.stat().st_size),tools.digest(p),'1'*64))+'\n')
                proof={'code_units_changed':16,'localized_labels':{name:{'code_units_changed':16} for name in MESSAGES}}
                return subprocess.CompletedProcess(command,0,stdout=json.dumps(proof))
            script=Path(command[2]);stage=Path(command[3])
            self.assertEqual(tools.digest(script),tools.pin()['after']['make_button_icons.py']['sha256'])
            self.assertNotEqual(script.parent,tools.VENDOR)
            self.assertEqual(command[-1],'xbox')
            lines=[]
            for name in sorted(ui.FONTS|{ui.LAYOUT,'System/Resource/ResourceSizeTable.Product.143.Nin_NX_NVN.rsizetable.zs'}):
                p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'synthetic output '+name.encode())
                lines.append('\t'.join((name,str(p.stat().st_size),tools.digest(p),'1'*64)))
            (stage/'manifest.tsv').write_text('\n'.join(lines)+'\n')
            return subprocess.CompletedProcess(command,0)
        publish=bundle.publish_no_replace if sys.platform=='linux' else lambda stage,destination:stage.rename(destination)
        with mock.patch.object(bundle,'publish_no_replace',side_effect=publish),mock.patch.object(ui,'new_destination',side_effect=lambda p:Path(p)),mock.patch.object(bundle,'GAME',{'romfs_content':'fixture','romfs_files':0}),mock.patch.object(ui.subprocess,'run',side_effect=run),mock.patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):
            ui.prepare(rom,tools.VENDOR,destination,Path(sys.executable))
        record=json.loads((destination/'xbox-ui.json').read_text())
        self.assertEqual(record['tool_derivation']['glyph_count'],34)
        self.assertEqual(record['resources'],ui.manifest(destination))
        self.assertFalse(record['hardware_validated']);self.assertEqual(len(commands),3)
        self.assertEqual(record['context_labels']['code_units_changed'],16)
        self.assertEqual(len(record['context_labels']['localized_labels']),15)
        self.assertEqual(len(record['resources']),21)
        self.assertEqual((rom/'romfs.bin').read_bytes(),b'synthetic')
        self.assertFalse(any(self.root.glob('.xbox34-tools-*')))

if __name__=='__main__':unittest.main()
