import subprocess
import tempfile
import unittest
from pathlib import Path


class BuildPaths(unittest.TestCase):
    def test_paths_are_literal_and_do_not_execute_shell_substitution(self):
        scratch = Path.cwd()/'.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory).resolve()
            source = root/'source with spaces'
            (source/'tools').mkdir(parents=True)
            (source/'tools/build_from_xci.sh').write_text('printf "%s\\0" "$@"\n')
            marker = root/'must-not-exist'
            xci = 'own dump $(touch '+str(marker)+').xci'
            keys, out = 'keys file', 'build output'
            script = Path(__file__).with_name('totk_build_inner.sh').resolve()
            result = subprocess.run(['bash', str(script), str(source), xci, keys, out, '-O1', '1'],
                                    check=True, capture_output=True)
            args = result.stdout.decode().split('\0')[:-1]
            self.assertEqual(args, [xci, keys, '--out', out, '--jobs', '4', '--gen-jobs', '3',
                                    '--gen-opt', '-O1', '--skip-extract'])
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
