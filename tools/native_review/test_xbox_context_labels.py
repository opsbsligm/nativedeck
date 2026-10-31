"""ROM-free regression for the literal inactive-button labels missed by glyph replacement."""
import hashlib
import struct
import unittest
from xbox_context_labels import LABELS, MEMBER, patch_archive, patch_layout


def layout(labels=None):
    labels = LABELS if labels is None else labels
    sections = []
    for name, pair in labels.items():
        pane = bytearray(140)
        pane[:4] = b'txt1'
        struct.pack_into('<I', pane, 4, len(pane))
        pane[12:12+len(name)] = name.encode()
        struct.pack_into('<I', pane, 100, 136)
        pane[136:140] = pair[0].encode('utf-16le')+b'\0\0'
        sections.append(pane)
    header = bytearray(20)
    header[:6] = b'FLYT\xff\xfe'
    struct.pack_into('<HIIH', header, 6, 20, 0x09000000, 20+140*len(sections), len(sections))
    return bytes(header)+b''.join(sections)


class ContextLabels(unittest.TestCase):
    def test_all_four_physical_positions_and_companion_variant(self):
        original = layout()
        changed, proof = patch_layout(original)
        self.assertEqual(proof['code_units_changed'], 16)
        self.assertFalse(proof['geometry_changed'])
        self.assertEqual(len(changed), len(original))
        allowed = set()
        for change in proof['changes']:
            at = change['offset']
            allowed.update((at, at+1))
            self.assertEqual(changed[at:at+4], change['after'].encode('utf-16le')+b'\0\0')
        self.assertTrue({i for i,(a,b) in enumerate(zip(original,changed)) if a!=b} <= allowed)
        self.assertEqual(proof['before_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(proof['after_sha256'], hashlib.sha256(changed).hexdigest())
        actual = {c['pane']: c['after'] for c in proof['changes']}
        self.assertEqual([actual[k] for k in ('T_X_00','T_Y_00','T_B_00')], ['Y','X','A'])
        self.assertEqual([actual[k] for k in ('T_X_02','T_Y_03','T_B_01')], ['Y','X','A'])
        self.assertEqual([actual[k] for k in ('T_A_01','T_X_01','T_Y_01')], ['B','Y','X'])
        self.assertEqual(actual['T_Plus_00'], '\ue04b')

    def test_unrelated_archive_members_remain_byte_identical(self):
        original = b'other archive data'+layout()+b'unrelated texture data'
        lo = len(b'other archive data'); hi = len(original)-len(b'unrelated texture data')
        changed, _ = patch_archive(original, {MEMBER:(lo,hi)})
        self.assertEqual(changed[:lo], original[:lo])
        self.assertEqual(changed[hi:], original[hi:])

    def test_missing_duplicate_and_already_changed_panes_refused(self):
        missing = dict(LABELS); missing.pop('T_X_00')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            patch_layout(layout(missing))
        original = bytearray(layout())
        original[20+140+12:20+140+44] = original[20+12:20+44]
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            patch_layout(bytes(original))
        changed, _ = patch_layout(layout())
        with self.assertRaisesRegex(ValueError, 'Unexpected original'):
            patch_layout(changed)

    def test_truncation_versions_offsets_and_nonterminated_text_refused(self):
        for offset, fmt, value in ((8,'I',0x08000000), (12,'I',1), (6,'H',0),
                                    (24,'I',0), (120,'I',0), (120,'I',0xffffffff),
                                    (158,'H',0x41)):
            with self.subTest(offset=offset):
                bad = bytearray(layout()); struct.pack_into('<'+fmt, bad, offset, value)
                with self.assertRaises(ValueError):patch_layout(bytes(bad))
        with self.assertRaises(ValueError):patch_layout(layout()[:-1])
        with self.assertRaises(ValueError):patch_archive(layout(), {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
