import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from native_binary_check import inspect, InvalidElf


@unittest.skipUnless(sys.platform.startswith('linux'), 'Real ELF fixtures require Linux')
class NativeBinaryCheck(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, count):
        cc = shutil.which(os.environ.get('CC', 'cc'))
        self.assertIsNotNone(cc, 'A native C compiler is required for this check')
        src, binary = self.root/'test.c', self.root/'test'
        src.write_text('const unsigned long g_ftab_count = ' + str(count) + ';\n'
                       'int main(void) { return 0; }\n')
        subprocess.run([cc, '-O0', str(src), '-o', str(binary)], check=True, capture_output=True)
        return binary

    def test_real_native_elf_with_zero_table_is_rejected(self):
        result = inspect(self.build(0), True)
        self.assertTrue(result['elf64_x86_64'])
        self.assertFalse(result['inspection_passed'])
        self.assertIn('empty_game_function_table_runtime_probe_only', result['errors'])

    def test_nonzero_counter_does_not_claim_release_or_playability(self):
        result = inspect(self.build(123), True)
        self.assertEqual(result['function_counters']['g_ftab_count'], 123)
        self.assertTrue(result['inspection_passed'])
        self.assertFalse(result['release_accepted'])
        self.assertFalse(result['playability_validated'])

    def test_truncated_and_wrong_architecture_are_rejected(self):
        binary = self.build(1)
        data = bytearray(binary.read_bytes())
        data[18:20] = (183).to_bytes(2, 'little')
        binary.write_bytes(data)
        with self.assertRaises(InvalidElf):
            inspect(binary, True)
        binary.write_bytes(b'\x7fELF')
        with self.assertRaises(InvalidElf):
            inspect(binary, True)


if __name__ == '__main__':
    unittest.main()
