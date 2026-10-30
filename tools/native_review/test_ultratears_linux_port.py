"""Checks of failure boundaries; fixtures are text and are never linked or run as a game."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

PORT = Path(__file__).resolve().parents[2] / 'ports/ultratears-linux/overlay/tools'


def module(name):
    spec = importlib.util.spec_from_file_location(name, PORT/(name+'.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LinuxLinkAudit(unittest.TestCase):
    def setUp(self):
        self.audit = module('audit_linux_runtime')
        self.report = '\n'.join('undefined symbol: '+s+'\t(audit.so)' for s in self.audit.EXPECTED)

    def test_only_real_game_table_dependencies_are_allowed(self):
        self.assertEqual(len(self.audit.inspect_report(self.report)), 9)
        with self.assertRaises(ValueError):
            self.audit.inspect_report(self.report+'\nundefined symbol: VirtualAlloc\t(audit.so)')

    def test_missing_shared_library_is_rejected(self):
        with self.assertRaises(ValueError):
            self.audit.inspect_report(self.report+'\nlibSDL3.so.0 => not found')

    def test_compatibility_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            self.audit.inspect_report(self.report+'\nlibwine.so => /lib/libwine.so')


class LinuxInputs(unittest.TestCase):
    def setUp(self):
        self.inputs = module('linux_inputs')
        self.tmp = tempfile.TemporaryDirectory(prefix='ultratears-input-check-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write_tables(self):
        for name, (lo, _) in self.inputs.BASES.items():
            d = self.root/name
            d.mkdir()
            (d/(name+'_table.c')).write_text(
                'const uint64_t '+name+'_fn_addrs[] = {0x'+format(lo,'x')+'};\n'
                'const GuestFn '+name+'_fn_ptrs[] = {f_'+format(lo,'x')+'};\n'
                'const uint64_t '+name+'_fn_count = 1;\n')
            (d/(name+'_0.c')).write_text('// synthetic fixture; never compiled\n')

    def test_reject_missing_or_empty_tables(self):
        with self.assertRaises(ValueError):
            self.inputs.generated_files(self.root)
        self.write_tables()
        self.assertEqual(len(self.inputs.generated_files(self.root)), 6)
        p = self.root/'main/main_table.c'
        p.write_text(p.read_text().replace('_fn_count = 1', '_fn_count = 0'))
        with self.assertRaises(ValueError):
            self.inputs.generated_files(self.root)

    def test_reject_table_count_pointer_and_address_mismatch(self):
        self.write_tables()
        p = self.root/'main/main_table.c'
        original = p.read_text()
        for old, new in [('_fn_count = 1','_fn_count = 2'), ('{f_800000000}', '{f_800000004}'),
                         ('{0x800000000}', '{0x1}')]:
            p.write_text(original.replace(old,new))
            with self.assertRaises(ValueError):
                self.inputs.generated_files(self.root)

    def test_reject_injected_or_missing_chunk(self):
        self.write_tables()
        (self.root/'main/extra.c').write_text('unexpected')
        with self.assertRaises(ValueError):
            self.inputs.generated_files(self.root)
        (self.root/'main/extra.c').unlink()
        (self.root/'main/main_0.c').unlink()
        with self.assertRaises(ValueError):
            self.inputs.generated_files(self.root)

    def test_version_check_hashes_bytes_instead_of_file_names(self):
        p=self.root/'main'; p.write_bytes(b'synthetic fixture')
        with mock.patch.object(self.inputs, 'expected', return_value={'EXEFS':{'main':self.inputs.digest(p)}}):
            self.assertTrue(self.inputs.check_exefs(self.root))
            p.write_bytes(b'tampered fixture')
            with self.assertRaises(ValueError):
                self.inputs.check_exefs(self.root)

    def test_manifest_detects_stale_or_modified_generated_code(self):
        self.write_tables()
        with mock.patch.object(self.inputs,'check_exefs',return_value={'main':'fixture'}), \
             mock.patch.object(self.inputs,'lifter_fingerprints',return_value={'generator':'fixture'}):
            self.inputs.seal_generated(self.root, self.root)
            self.assertEqual(len(self.inputs.verify_generated(self.root,self.root)),6)
            (self.root/'main/main_0.c').write_text('// changed fixture')
            with self.assertRaises(ValueError):
                self.inputs.verify_generated(self.root,self.root)

    def test_public_fingerprints_are_read_without_importing_windows_setup(self):
        tools=self.root/'tools'; tools.mkdir()
        (tools/'setup.py').write_text("raise RuntimeError('must not import')\nEXEFS={'main':'hash'}\n"
                                     "ROMFS_FILES=1\nROMFS_BYTES=2\nROMFS_CONTENT='content'\n")
        with mock.patch.object(self.inputs,'ROOT',self.root):
            self.assertEqual(self.inputs.expected()['ROMFS_CONTENT'],'content')


class LinuxBuildPriority(unittest.TestCase):
    def test_affinity_is_intersected_with_available_cpus(self):
        proc=module('linux_process')
        with mock.patch.object(proc.os,'sched_getaffinity',return_value={4,5},create=True):
            command=proc.limited_command(['tool'],1)
            self.assertEqual(command[:6],['nice','-n','10','taskset','--cpu-list','4'])
            with self.assertRaises(ValueError):
                proc.limited_command(['tool'],0)


if __name__ == '__main__':
    unittest.main()
