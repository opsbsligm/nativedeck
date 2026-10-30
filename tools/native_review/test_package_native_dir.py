import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith('linux'), 'Uses Linux coreutils and tar')
class PackageNativeDirectory(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd()/'.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root/'game directory'
        self.source.mkdir()
        (self.source/'asset with spaces').write_bytes(b'local fixture')
        self.archive = self.root/'game.tar.zst'
        self.manifest = self.root/'manifest.sha256'
        self.script = Path(__file__).with_name('package_native_dir.sh').resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def run_package(self, env=None):
        return subprocess.run(['bash', str(self.script), str(self.source), str(self.archive),
                               str(self.manifest)], env=env, capture_output=True)

    @unittest.skipUnless(shutil.which('zstd'), 'Archive round trip needs zstd')
    def test_space_in_resource_name_survives_manifest_and_archive(self):
        result = self.run_package()
        self.assertEqual(result.returncode, 0, result.stderr)
        subprocess.run(['sha256sum', '--quiet', '-c', str(self.manifest)],
                       cwd=self.source, check=True)
        restored = self.root/'restored'
        restored.mkdir()
        subprocess.run(['tar', '--zstd', '-xf', str(self.archive), '-C', str(restored)], check=True)
        self.assertEqual((restored/'game directory/asset with spaces').read_bytes(), b'local fixture')

    def test_archive_failure_cannot_publish_manifest_or_success(self):
        tools = self.root/'tools'
        tools.mkdir()
        tar = tools/'tar'
        tar.write_text('#!/bin/sh\nexit 42\n')
        tar.chmod(0o755)
        env = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'])
        result = self.run_package(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(result.stdout, b'')
        self.assertEqual(list(self.root.glob('*.partial.*')), [])


if __name__ == '__main__':
    unittest.main()
