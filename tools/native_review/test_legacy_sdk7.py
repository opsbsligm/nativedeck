import tempfile
import unittest
from pathlib import Path

from legacy_sdk7 import BUILD_ID, MAIN_BASE, verify_exefs, verify_main


class LegacySdk7(unittest.TestCase):
    def test_matching_claimed_id_cannot_admit_a_forged_main(self):
        scratch = Path.cwd()/'.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            main = Path(directory)/'main'
            data = bytearray(256)
            data[:4] = b'NSO0'
            data[0x40:0x60] = bytes.fromhex(BUILD_ID).ljust(32, b'\0')
            main.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'hash'):
                verify_main(main, MAIN_BASE, BUILD_ID)

    def test_other_build_ids_and_bases_are_refused_before_reading_input(self):
        for base, build in [(MAIN_BASE+4096, BUILD_ID), (MAIN_BASE, 'cd57b23fa4bbad65')]:
            with self.assertRaisesRegex(ValueError, 'base or build ID'):
                verify_main(Path('does-not-exist'), base, build)

    def test_additional_sdk_module_is_not_silently_admitted(self):
        with self.assertRaisesRegex(ValueError, 'exactly'):
            verify_exefs(Path('does-not-exist'), ['main', 'subsdk0', 'subsdk1', 'sdk'])


if __name__ == '__main__':
    unittest.main()
