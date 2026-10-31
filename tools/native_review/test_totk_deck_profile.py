import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from apply_totk_deck_profile import PROFILE


class DesiredLanguage(unittest.TestCase):
    def test_native_language_code_matches_settings_and_cannot_overflow(self):
        compiler = shutil.which('c++') or shutil.which('clang++') or shutil.which('g++')
        self.assertIsNotNone(compiler, 'A C++ compiler is required to verify the runtime header')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'language.cpp'
            source.write_text('#include "deck_language.h"\nint main() { auto x=deck_desired_language(); '
                              'return std::fwrite(&x,1,8,stdout)==8 ? 0 : 1; }\n')
            binary = folder/'language'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(PROFILE.parent), str(source), '-o', str(binary)], check=True)
            for setting, expected in [(None, 'zh-Hans'), ('', 'zh-Hans'), ('en-US', 'en-US'),
                                      ('ja', 'ja'), ('zh-Hant', 'zh-Hant'), ('x'*4096, 'zh-Hans')]:
                with self.subTest(setting=setting[:20] if setting else setting):
                    env = dict(os.environ)
                    env.pop('TOTK_LANG', None)
                    if setting is not None:
                        env['TOTK_LANG'] = setting
                    result = subprocess.run([str(binary)], env=env, capture_output=True, check=True)
                    self.assertEqual(result.stdout, expected.encode().ljust(8, b'\0'))


if __name__ == '__main__':
    unittest.main()
