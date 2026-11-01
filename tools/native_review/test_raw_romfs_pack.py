"""Offline synthetic fixtures; no game resources or upstream source copies.

Optional integration: RAW_ROMFS_INDEX_SCRIPT=/local/make_romfs_index.py
python3 -B -m unittest -v test_raw_romfs_pack
Without it, a fixed-output protocol double checks the index-tool handoff.
All scratch files stay in a named directory beside this module and are removed.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from raw_romfs_pack import load_profile, pack, read_entries

NONE = 0xffffffff
EXPECTED_PACKED = b'beta' + b'\0' * 12 + b'alpha' + b'\0' * 11
EXPECTED_FILES = [
    {'path': 'Dir/b.bin', 'offset': 0, 'size': 4},
    {'path': 'a.bin', 'offset': 16, 'size': 5},
    {'path': 'z-empty', 'offset': 32, 'size': 0},
]
# Frozen independently from the three explicit payloads: beta, alpha, empty.
CONTENT = '6be0e8966f978826564b232f1292a7224aede5ff94b00c601e5d1ada4e54dc7b'
# TOTKRFS1: 3 entries, string table at 96; names at 0, 10, 16.
EXPECTED_RUNTIME = bytes.fromhex(
    '544f544b5246533103000000000000006000000000000000'
    '00000000000000000400000000000000000000000a000000'
    '100000000000000005000000000000000a00000006000000'
    '200000000000000000000000000000001000000008000000'
    '4469722f622e62696e00612e62696e007a2d656d70747900')
PROFILE = {'romfs_files': 3, 'romfs_bytes': 9, 'romfs_content': CONTENT}


def fixture(path, metadata_after=False):
    """Small hand-laid tree. File metadata order differs from packed path order."""
    dirs = (struct.pack('<6I', NONE, NONE, 24, 0, 0, 0)
            + struct.pack('<6I', 0, NONE, NONE, 80, 0, 3) + b'Dir\0')
    files = (struct.pack('<IIQQII', 0, 40, 32, 5, 0, 5) + b'a.bin\0\0\0'
             + struct.pack('<IIQQII', 0, NONE, 0, 0, 0, 7) + b'z-empty\0'
             + struct.pack('<IIQQII', 24, NONE, 0, 4, 0, 5) + b'b.bin\0\0\0')
    payload = b'beta' + b'\0' * 28 + b'alpha'
    if metadata_after:
        # Payload ends exactly at the first metadata boundary, offset 117.
        header = (80, 117, 4, 121, 52, 173, 4, 177, 120, 80)
        blob = struct.pack('<10Q', *header) + payload + b'\0'*4 + dirs + b'\0'*4 + files
    else:
        header = (80, 80, 4, 84, 52, 136, 4, 140, 120, 272)
        blob = (struct.pack('<10Q', *header) + b'\0'*4 + dirs + b'\0'*4
                + files + b'\0'*12 + payload)
    path.write_bytes(blob)
    return header


class RawRomFSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(
            prefix='raw-romfs-pack-tests-', dir=Path(__file__).resolve().parent)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.scratch.name)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'synthetic.raw'
        self.header = fixture(self.image)
        self.out = self.root / 'packed'
        self.index_tool = self.root / 'fixture_index_tool.py'
        # A literal-response contract double, deliberately NOT another index implementation.
        self.index_tool.write_text(
            'import json, pathlib, sys\n'
            'root = pathlib.Path(sys.argv[1])\n'
            'doc = json.loads((root / "index.json").read_text())\n'
            f'assert doc["files"] == {EXPECTED_FILES!r}\n'
            f'assert doc["content_sha256"] == {CONTENT!r}\n'
            f'(root / "runtime-index.bin").write_bytes({EXPECTED_RUNTIME!r})\n')
        if os.environ.get('RAW_ROMFS_INDEX_SCRIPT'):
            self.index_tool = Path(os.environ['RAW_ROMFS_INDEX_SCRIPT']).resolve()

    def mutate(self, offset, fmt, value):
        blob = bytearray(self.image.read_bytes())
        struct.pack_into(fmt, blob, offset, value)
        self.image.write_bytes(blob)

    def convert(self, profile=None, tool=None):
        return pack(self.image, self.out, PROFILE if profile is None else profile,
                    self.index_tool if tool is None else tool, progress=lambda _: None)

    def assert_outputs(self):
        self.assertEqual((self.out / 'romfs.bin').read_bytes(), EXPECTED_PACKED)
        self.assertEqual((self.out / 'runtime-index.bin').read_bytes(), EXPECTED_RUNTIME)
        doc = json.loads((self.out / 'index.json').read_text())
        self.assertEqual(doc['files'], EXPECTED_FILES)
        self.assertEqual(doc['content_sha256'], CONTENT)
        self.assertEqual(doc['status'], 'pass')
        self.assertFalse(self.out.with_suffix('.partial').exists())

    def test_packed_bytes_and_indexes_metadata_before(self):
        result = self.convert()
        self.assertEqual((result['files'], result['bytes']), (3, 32))
        self.assertFalse(result['hardware_validated'])
        self.assert_outputs()

    def test_packed_bytes_and_indexes_metadata_after(self):
        fixture(self.image, metadata_after=True)
        self.convert()
        self.assert_outputs()

    def test_metadata_can_end_exactly_at_payload_start(self):
        blob = bytearray(self.image.read_bytes())
        del blob[260:272]
        struct.pack_into('<Q', blob, 72, 260)
        self.image.write_bytes(blob)
        self.convert()
        self.assert_outputs()

    def test_data_must_not_point_into_header(self):
        for value in (0, 1, 79):
            with self.subTest(value=value):
                fixture(self.image)
                self.mutate(72, '<Q', value)
                with self.assertRaisesRegex(ValueError, 'bounds'):
                    read_entries(self.image)

    def test_data_outside_image(self):
        self.mutate(72, '<Q', 310)
        with self.assertRaisesRegex(ValueError, 'bounds'):
            read_entries(self.image)

    def test_metadata_overlap_each_neighbor(self):
        for field, value in ((3, 83), (5, 135), (7, 139)):
            with self.subTest(field=field):
                fixture(self.image)
                self.mutate(field*8, '<Q', value)
                with self.assertRaisesRegex(ValueError, 'Overlapping'):
                    read_entries(self.image)

    def test_metadata_header_and_eof_bounds(self):
        for field, value in ((1, 79), (7, 308), (4, 128*1024**2+1),
                             (8, 256*1024**2+1)):
            with self.subTest(field=field):
                fixture(self.image)
                self.mutate(field*8, '<Q', value)
                with self.assertRaises(ValueError):
                    read_entries(self.image)

    def test_data_inside_metadata(self):
        for value in (80, 81, 84, 139, 259):
            with self.subTest(value=value):
                fixture(self.image)
                self.mutate(72, '<Q', value)
                with self.assertRaisesRegex(ValueError, 'inside metadata'):
                    read_entries(self.image)

    def test_payload_cannot_cross_trailing_metadata(self):
        header = fixture(self.image, metadata_after=True)
        self.mutate(header[7]+16, '<Q', 6)  # alpha would consume metadata byte 117
        with self.assertRaisesRegex(ValueError, 'outside RomFS'):
            read_entries(self.image)

    def test_payload_extent_and_name_bounds(self):
        for offset, fmt, value in ((148, '<Q', 1<<63), (156, '<Q', 6),
                                   (248, '<I', 999)):
            with self.subTest(offset=offset):
                fixture(self.image)
                self.mutate(offset, fmt, value)
                with self.assertRaises(ValueError):
                    read_entries(self.image)

    def test_short_and_unsupported_header(self):
        self.image.write_bytes(b'\0'*79)
        with self.assertRaisesRegex(ValueError, 'Short'):
            read_entries(self.image)
        fixture(self.image)
        self.mutate(0, '<Q', 81)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            read_entries(self.image)

    def test_file_and_directory_cycles(self):
        for offset, value in ((144, 0), (112, 24), (116, 24)):
            with self.subTest(offset=offset):
                fixture(self.image)
                self.mutate(offset, '<I', value)
                with self.assertRaisesRegex(ValueError, 'Cyclic'):
                    read_entries(self.image)

    def test_wrong_parent_and_truncated_pointers(self):
        for offset, value in ((140, 24), (108, 99), (96, 999), (92, 999)):
            with self.subTest(offset=offset):
                fixture(self.image)
                self.mutate(offset, '<I', value)
                with self.assertRaises(ValueError):
                    read_entries(self.image)

    def test_unsafe_names_and_invalid_utf8(self):
        for name in (b'../x1', b'/abcd', b'a\\bcd', b'a\0bcd', b'\xffabcd'):
            with self.subTest(name=name):
                fixture(self.image)
                blob = bytearray(self.image.read_bytes())
                blob[172:177] = name
                self.image.write_bytes(blob)
                with self.assertRaises(ValueError):
                    read_entries(self.image)

    def test_duplicate_file_path(self):
        blob = bytearray(self.image.read_bytes())
        struct.pack_into('<I', blob, 208, 5)
        blob[212:217] = b'a.bin'
        self.image.write_bytes(blob)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            read_entries(self.image)

    def test_file_directory_path_collision(self):
        blob = bytearray(self.image.read_bytes())
        struct.pack_into('<I', blob, 168, 3)
        blob[172:175] = b'Dir'
        self.image.write_bytes(blob)
        with self.assertRaisesRegex(ValueError, 'collision'):
            read_entries(self.image)

    def test_full_payload_hash_rejects_same_size_corruption(self):
        blob = bytearray(self.image.read_bytes())
        blob[-1] ^= 1
        self.image.write_bytes(blob)
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.convert()
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_suffix('.partial').exists())

    def test_profile_count_and_byte_floor_gates(self):
        for key, value in (('romfs_files', 4), ('romfs_bytes', 33)):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.convert({**PROFILE, key: value})
                self.assertFalse(self.out.exists())
                self.assertFalse(self.out.with_suffix('.partial').exists())

    def test_input_symlink_rejected(self):
        link = self.root / 'link.raw'
        link.symlink_to(self.image)
        with self.assertRaisesRegex(ValueError, 'regular'):
            pack(link, self.out, PROFILE, self.index_tool)

    def test_existing_output_and_staging_are_not_modified(self):
        for path in (self.out, self.out.with_suffix('.partial')):
            with self.subTest(path=path.name):
                path.mkdir()
                marker = path / 'keep'
                marker.write_bytes(b'keep')
                with self.assertRaises((ValueError, FileExistsError)):
                    self.convert()
                self.assertEqual(marker.read_bytes(), b'keep')
                marker.unlink()
                path.rmdir()

    def test_failed_index_tool_cleans_only_own_staging(self):
        tool = self.root / 'failing_index.py'
        tool.write_text('raise SystemExit(7)\n')
        with self.assertRaises(subprocess.CalledProcessError):
            self.convert(tool=tool)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_suffix('.partial').exists())

    def test_missing_index_output_rejected(self):
        tool = self.root / 'noop_index.py'
        tool.write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'did not produce'):
            self.convert(tool=tool)
        self.assertFalse(self.out.with_suffix('.partial').exists())

    def test_source_change_gate(self):
        def change_after_metadata_read(image):
            rows = read_entries(image)
            os.utime(image, ns=(1, 1))
            return rows
        with patch('raw_romfs_pack.read_entries', side_effect=change_after_metadata_read):
            with self.assertRaisesRegex(ValueError, 'changed while packing'):
                self.convert()
        self.assertFalse(self.out.exists())

    def test_profile_ast_does_not_execute_code(self):
        profile = self.root / 'profile.py'
        profile.write_text('raise RuntimeError("must not execute")\nGAME = '+repr(PROFILE))
        self.assertEqual(load_profile(profile), PROFILE)
        for text in ('GAME = dict()', 'GAME = {}', 'GAME = 1',
                     'GAME = {}\nGAME = {}', 'OTHER = {}'):
            with self.subTest(text=text):
                profile.write_text(text)
                with self.assertRaises(ValueError):
                    load_profile(profile)

    def test_cli_from_other_working_directory(self):
        profile = self.root / 'profile.py'
        profile.write_text('GAME = '+repr(PROFILE))
        result = subprocess.run([
            sys.executable, '-B', str(Path(__file__).with_name('raw_romfs_pack.py').resolve()),
            '--romfs', str(self.image), '--out', str(self.out),
            '--game-profile-source', str(profile), '--index-script', str(self.index_tool)],
            cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])['files'], 3)
        self.assert_outputs()


if __name__ == '__main__':
    unittest.main()
