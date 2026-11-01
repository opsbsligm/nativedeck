"""Cover both real ldd interpreter formats without relaxing library boundaries."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import native_dependencies as native


class NativeLoaderDependencies(unittest.TestCase):
    def check(self, text, interpreter='/lib64/ld-linux-x86-64.so.2', loader_valid=True):
        def inspected(path):
            if str(path)=='/fixture/game':
                return {'interpreter':interpreter,'inspection_passed':True}
            return {'interpreter':None,'inspection_passed':loader_valid}
        with patch.object(native,'inspect',side_effect=inspected), patch.object(native.subprocess,'run',
                return_value=SimpleNamespace(stdout=text)):
            return native.dependencies(Path('/fixture/game'),[])

    def test_both_system_interpreter_formats(self):
        for line in ('/lib64/ld-linux-x86-64.so.2 (0x1000)',
                     '/lib64/ld-linux-x86-64.so.2 => /usr/lib/ld-linux-x86-64.so.2 (0x1000)'):
            with self.subTest(line=line):self.assertEqual(self.check(line),{})

    def test_absolute_non_interpreter_dependency_stays_rejected(self):
        with self.assertRaisesRegex(ValueError,'Non-native/unsafe'):
            self.check('/lib64/libc.so.6 => /usr/lib/libc.so.6 (0x1000)')

    def test_interpreter_must_be_native_and_resolve_to_system_directory(self):
        for path in ('/home/deck/private/ld-linux-x86-64.so.2',
                     '/home/deck/.wine/ld-linux-x86-64.so.2'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError,'Invalid native system interpreter'):
                self.check('/lib64/ld-linux-x86-64.so.2 => '+path+' (0x1000)')
        with self.assertRaisesRegex(ValueError,'Invalid native system interpreter'):
            self.check('/lib64/ld-linux-x86-64.so.2 => /usr/lib/ld-linux-x86-64.so.2 (0x1000)',loader_valid=False)

    def test_mismatched_or_compat_interpreter_stays_rejected(self):
        with self.assertRaisesRegex(ValueError,'Non-native/unsafe'):
            self.check('/lib/other-loader => /usr/lib/ld-linux-x86-64.so.2 (0x1000)')
        with self.assertRaisesRegex(ValueError,'Invalid native system interpreter'):
            self.check('/home/deck/.wine/ld-linux-x86-64.so.2 => /usr/lib/ld-linux-x86-64.so.2 (0x1000)',
                       interpreter='/home/deck/.wine/ld-linux-x86-64.so.2')


if __name__=='__main__':unittest.main()
