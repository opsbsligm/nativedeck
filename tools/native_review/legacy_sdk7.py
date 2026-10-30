"""Exact input profile for the local BOTW 1.6.0 port, with optional sites omitted.

This profile is intentionally separate from newer builds' address tables. It
does not mark an unknown build compatible and never edits an NSO or a library.
"""
import hashlib
from pathlib import Path

MAIN_BASE = 0x7000000000
BUILD_ID = '8e9978d50bdd20b4c8395a106c27ffde'
PINS = {
    'main': '15cfca7b89348956f85d945fade2e215a6af5991ed1071e181f97ca72f7ae20b',
    'subsdk0': 'd22d98656a19be240b554e7db8d69126d6427232521238d665aec3509087f2cf',
    'sdk': '754cf4b581d749fbe3d457cf66497b141ef994cf592d247919d64a37dcc30d27',
}


def verify_main(path, base, build_id):
    path = Path(path)
    claimed = bytes.fromhex(build_id)
    expected_id = bytes.fromhex(BUILD_ID).ljust(32, b'\0')
    if base != MAIN_BASE or len(claimed) > 32 or claimed.ljust(32, b'\0') != expected_id:
        raise ValueError('SDK7 profile: unexpected main base or build ID')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != PINS['main']:
        raise ValueError('SDK7 profile: original main hash does not match')
    return '1.6.0', {}


def verify_exefs(exefs, names):
    if list(names) != list(PINS):
        raise ValueError('SDK7 profile requires exactly main, subsdk0, sdk')
    for name, expected in PINS.items():
        with (Path(exefs)/name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('SDK7 profile: original module hash does not match: '+name)
