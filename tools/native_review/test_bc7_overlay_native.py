# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline bridge: production-bound BC7 cache tests; native execution is Linux-only."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'ports/ultratears-linux/cache-tests'


class BC7OverlayNativeTests(unittest.TestCase):
    def run_public(self, integrity_only=False):
        with tempfile.TemporaryDirectory(prefix='bc7-ci-bridge-') as temporary:
            summary = Path(temporary) / 'summary.json'
            command = [sys.executable, '-B', str(PUBLIC / 'run_tests.py'), '--json-out', str(summary)]
            if integrity_only:
                command.append('--integrity-only')
            result = subprocess.run(command, cwd=temporary, text=True, capture_output=True,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(summary.read_text())
            self.assertTrue(data['production_patch_bound'])
            self.assertTrue(data['temporary_files_cleaned'])
            self.assertEqual(data['integrity_checks_passed'], 4)
            self.assertEqual(data['skipped'], 0)
            self.assertEqual(data['candidate_sha256'], json.loads(
                (PUBLIC / 'manifest.json').read_text())['candidate_sha256'])
            return data

    def test_public_python_parses(self):
        scripts = sorted(PUBLIC.glob('*.py'))
        self.assertGreaterEqual(len(scripts), 4)
        for path in scripts:
            with self.subTest(script=path.name):
                ast.parse(path.read_text(), filename=path.name)

    def test_production_binding_and_public_integrity(self):
        data = self.run_public(integrity_only=True)
        self.assertEqual(data['passed'], 0)
        self.assertEqual(data['mode'], 'integrity-only')

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux C execution; portable binding/integrity still run')
    def test_linux_native_34_groups(self):
        data = self.run_public()
        self.assertEqual(data['platform'], 'linux')
        self.assertEqual(data['passed'], 34)
        self.assertEqual(len(data['tests']), 34)
        self.assertEqual(data['mode'], 'native')


if __name__ == '__main__':
    unittest.main()
