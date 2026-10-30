import tempfile
import unittest
from pathlib import Path

from settings_defaults import apply


class SettingsDefaults(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd()/'.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.path = Path(self.tmp.name)/'savagewind.ini'

    def tearDown(self):
        self.tmp.cleanup()

    def test_player_bindings_and_audio_survive_and_backup_matches(self):
        old = b'button_icons = xbox\ntext_language = auto\nvolume = 0.7\nbind_pad_a = south\n'
        self.path.write_bytes(old)
        self.assertTrue(apply(self.path))
        self.assertIn(b'text_language = CNzh', self.path.read_bytes())
        self.assertIn(b'volume = 0.7\nbind_pad_a = south', self.path.read_bytes())
        self.assertEqual(next((self.path.parent/'native-settings-backups').glob('*.ini')).read_bytes(), old)
        self.assertFalse(apply(self.path))

    def test_explicit_language_and_icons_are_preserved(self):
        old = b'text_language = TWzh\nbutton_icons = playstation\n'
        self.path.write_bytes(old)
        self.assertFalse(apply(self.path))
        self.assertEqual(self.path.read_bytes(), old)

    def test_duplicate_keys_are_rejected_without_changes(self):
        old = b'text_language = auto\ntext_language = USen\n'
        self.path.write_bytes(old)
        with self.assertRaises(ValueError):
            apply(self.path)
        self.assertEqual(self.path.read_bytes(), old)


if __name__ == '__main__':
    unittest.main()
