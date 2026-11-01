"""ROM-free regression for the literal inactive-button labels missed by glyph replacement."""
import hashlib
import struct
import unittest
from xbox_context_labels import LABELS, MEMBER, patch_archive, patch_layout, patch_messages


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


def messages(labels=None):
    labels = dict(LABELS if labels is None else labels)
    labels['unrelated_dialogue'] = ('A', 'A')
    entries=[];strings=[]
    for i,(name,pair) in enumerate(labels.items()):
        entries.append(bytes([len(name)])+name.encode()+struct.pack('<I',i))
        strings.append(pair[0].encode('utf-16le')+b'\0\0')
    lbl=struct.pack('<III',1,len(entries),12)+b''.join(entries)
    cursor=4+len(strings)*4;offsets=[]
    for string in strings:offsets.append(cursor);cursor+=len(string)
    txt=struct.pack('<I',len(strings))+struct.pack('<'+str(len(strings))+'I',*offsets)+b''.join(strings)
    result=bytearray(32);result[:10]=b'MsgStdBn\xff\xfe';result[12]=1
    struct.pack_into('<H',result,14,2)
    for tag,body in ((b'LBL1',lbl),(b'TXT2',txt)):
        result.extend(tag+struct.pack('<I',len(body))+bytes(8)+body)
        result.extend(bytes(-len(result)%16))
    struct.pack_into('<I',result,18,len(result))
    return bytes(result)


class ContextLabels(unittest.TestCase):
    def test_runtime_localization_overrides_receive_the_same_mapping(self):
        before=messages();after,proof=patch_messages(before)
        self.assertEqual(proof['code_units_changed'],16)
        self.assertFalse(proof['dialogue_changed'])
        allowed={i for row in proof['changes'] for i in (row['offset'],row['offset']+1)}
        self.assertTrue({i for i,(a,b) in enumerate(zip(before,after)) if a!=b}<=allowed)
        self.assertEqual(len(after),len(before))
        # An unrelated string also containing "A" is deliberately left untouched.
        self.assertEqual(before[-8:], b'A\0\0\0\0\0\0\0')
        self.assertEqual(after[-8:],before[-8:])
        self.assertEqual({r['pane']:r['after'] for r in proof['changes']},
                         {name:pair[1] for name,pair in LABELS.items()})

    def test_missing_or_wrong_localized_labels_fail_closed(self):
        missing=dict(LABELS);missing.pop('T_B_00')
        with self.assertRaisesRegex(ValueError,'incomplete'):patch_messages(messages(missing))
        wrong=dict(LABELS);wrong['T_X_00']=('Q','Y')
        with self.assertRaisesRegex(ValueError,'Unexpected localized'):patch_messages(messages(wrong))
        changed,_=patch_messages(messages())
        with self.assertRaisesRegex(ValueError,'Unexpected localized'):patch_messages(changed)

    def test_malformed_message_headers_and_text_extents_fail_closed(self):
        for offset,fmt,value in ((12,'B',0),(18,'I',1),(14,'H',99),(36,'I',0xffffffff),
                                 (52,'I',0xffffffff),(56,'I',0xffffffff)):
            with self.subTest(offset=offset):
                bad=bytearray(messages());struct.pack_into('<'+fmt,bad,offset,value)
                with self.assertRaises((ValueError,UnicodeDecodeError)):patch_messages(bytes(bad))

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
