import json
import os
import tempfile
import unittest
from pathlib import Path

from prepare_totk_nca import KEYS_LIMIT, PIN, REQUIRED_CONTENT_ID, private_stage, read_keys, validate_extraction, write_filtered_keys


class NativeNcaInputs(unittest.TestCase):
    def test_oversized_key_selection_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'wrong-key-input'
            with path.open('wb') as out:
                out.truncate(KEYS_LIMIT*2)
            with self.assertRaisesRegex(ValueError, '1 MiB limit'):
                read_keys(path)

    def test_private_key_filter_is_exclusive_and_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.umask(0)
            try:
                stage = private_stage(Path(tmp))
                self.assertEqual(stage.stat().st_mode & 0o777, 0o700)
                path = stage/'filtered'
                write_filtered_keys(path, {'header_key': '12'*32})
            finally:
                os.umask(old)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                write_filtered_keys(path, {'header_key': '34'*32})
            self.assertEqual(path.read_text(), 'header_key = '+'12'*32+'\n')

    def test_shipped_profile_has_the_complete_reference_module_set(self):
        pin = json.loads(PIN.read_text())
        self.assertEqual(pin['program_nca'], REQUIRED_CONTENT_ID+'.nca')
        self.assertEqual(set(pin['exefs_sha256']), {'main', 'main.npdm', 'rtld', 'sdk', 'subsdk0'})

    def test_old_keyset_is_rejected_before_material_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'keys'
            path.write_text('header_key = '+'12'*32+'\nmaster_key_0a = '+'34'*16+'\n')
            with self.assertRaisesRegex(ValueError, 'generation 0E'):
                read_keys(path)

    def test_case_insensitive_exported_names_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'keys'
            path.write_text('HEADER_KEY = '+'12'*32+'\nKEY_AREA_KEY_APPLICATION_0E = '+'34'*16+' # exported\n')
            keys = read_keys(path)
            self.assertIn('key_area_key_application_0e', keys)

    def test_duplicate_key_names_cannot_silently_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'keys'
            path.write_text('header_key = '+'12'*32+'\nHEADER_KEY = '+'34'*32+'\n')
            with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
                read_keys(path)

    def test_wrong_game_code_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'exefs').mkdir()
            (root/'exefs/main').write_bytes(b'not game code')
            with self.assertRaisesRegex(ValueError, 'does not match TOTK 1.0.0'):
                validate_extraction(root, {'exefs_sha256': {'main': '00'*32}})


if __name__ == '__main__':
    unittest.main()
