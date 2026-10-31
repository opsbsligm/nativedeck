#!/usr/bin/env python3
"""Offline focused CI: Python 3.14+, stdlib zstd; no pip/network/ROM or skips."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
if sys.version_info<(3,14):raise SystemExit('Xbox34 CI requires Python >=3.14 with compression.zstd; no skip permitted')
from compression import zstd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from xbox34_tools import fonttools_path
sys.path.insert(0,str(fonttools_path()))
# Job-local scratch only; never default /tmp or source/installation state.
scratch=Path(os.environ.get('XBOX34_TEST_TMP',str(HERE.parents[1]/'.xbox34-test-tmp'))).absolute()
scratch.mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(scratch);tempfile.tempdir=str(scratch)
sys.path.insert(0,str(HERE.parents[1]/'ports/ultratears-linux/xbox/tests'))
suite=unittest.defaultTestLoader.loadTestsFromName('test_xbox34_tools')
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.testsRun>=6 and result.wasSuccessful() and not result.skipped else 1)
