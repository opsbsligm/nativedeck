import json
import tempfile
import unittest
from pathlib import Path

from prepare_totk_nca import PIN, REQUIRED_CONTENT_ID, read_keys, validate_extraction


class NativeNcaInputs(unittest.TestCase):
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
