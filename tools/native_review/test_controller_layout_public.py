"""Bridge renderer-independent public anchor tests into existing review-tools CI.

Only the synthetic suite is loaded. No private metadata, game file, resource
patch builder, renderer compilation, network or device connection is used.
"""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'ports/ultratears-linux/controller-layout'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load public controller tests: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tests(loader, standard_tests, pattern):
    # The shipped public suite imports anchor_contract by its standalone name.
    # Preserve any unrelated module with that name in the existing test process.
    previous = sys.modules.get('anchor_contract')
    try:
        sys.modules['anchor_contract'] = _load('anchor_contract', PUBLIC/'anchor_contract.py')
        module = _load('controller_layout_public_tests', PUBLIC/'test_anchor_contract.py')
        suite = loader.loadTestsFromModule(module)
    finally:
        if previous is None:
            sys.modules.pop('anchor_contract', None)
        else:
            sys.modules['anchor_contract'] = previous
    if suite.countTestCases() < 7:
        raise RuntimeError('Public controller anchor suite unexpectedly contains fewer than seven tests')
    return suite
