"""ROM-free tests for tutorial step boundaries and binary-channel preservation."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import unittest

PUBLIC = Path(__file__).resolve().parents[2] / 'ports/ultratears-linux/controller-layout'


def load_tool():
    names = ('resource_layout', 'anchor_contract', 'build_controller_patch', 'build_action_guide_patch')
    previous = {name: sys.modules.get(name) for name in names}
    try:
        for name in names:
            spec = importlib.util.spec_from_file_location(name, PUBLIC / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return sys.modules[names[-1]]
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


T = load_tool()


class ActionGuidePatch(unittest.TestCase):
    def test_optimized_python_cannot_disable_input_guards(self):
        result = subprocess.run([sys.executable, '-O', '-B', str(PUBLIC / 'build_action_guide_patch.py'),
                                 '--input-root', str(PUBLIC / 'absent-private-input'),
                                 '--anchors', str(PUBLIC / 'absent-private-anchors'),
                                 '--output', str(PUBLIC / 'must-never-be-created')],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Do not use Python -O', result.stderr)
        self.assertFalse((PUBLIC / 'must-never-be-created').exists())

    def test_duplicate_frame_switch_is_right_continuous(self):
        raw = T.curve('translation_x', [12., 45., -7.])
        _, target, dtype, count, _, offset = struct.unpack_from('<BBHHHI', raw)
        self.assertEqual((target, dtype, count, offset), (0, 2, 5, 12))
        keys = [dict(zip(('frame', 'value', 'slope'), struct.unpack_from('<fff', raw, offset + i * 12)))
                for i in range(count)]
        channel = {'data_type': 2, 'keys': keys}
        for frame, expected in ((0., 12.), (.999, 12.), (1., 45.), (1.999, 45.), (2., -7.)):
            self.assertAlmostEqual(T.P.eval_channel(channel, frame), expected)

    def test_interpolation_and_nonzero_slopes_are_rejected(self):
        for values, slopes in (((0., 1.), (0., 0.)), ((1., 1.), (1., 0.))):
            channel = {'data_type': 2, 'property': 'width',
                       'keys': [{'frame': float(i), 'value': v, 'slope': s}
                                for i, (v, s) in enumerate(zip(values, slopes))]}
            with self.assertRaises(AssertionError):
                T.held_only(channel)

    def test_binary_rebuild_keeps_visibility_and_other_transforms(self):
        # Separate source encoding: one FLPA with x/y/z and one FLVI tag.
        def source_curve(target, value):
            return struct.pack('<BBHHHIfff', 0, target, 2, 1, 0, 12, 0., value, 0.)
        flpa = T.tag_bytes('FLPA', [source_curve(0, 1.), source_curve(1, 2.), source_curve(2, 77.)])
        visible = struct.pack('<BBHHHIfHH', 0, 0, 1, 1, 0, 12, 0., 1, 0)
        flvi = T.tag_bytes('FLVI', [visible])
        entry = bytearray(40)
        entry[:len(T.ROOT)] = T.ROOT.encode()
        entry[28] = 2
        struct.pack_into('<II', entry, 32, 40, 40 + len(flpa))
        entry.extend(flpa + flvi)
        def archive(raw_entry):
            payload = bytearray(24)
            payload[:4] = b'pai1'
            struct.pack_into('<H', payload, 8, 32)
            struct.pack_into('<H', payload, 14, 1)
            struct.pack_into('<I', payload, 16, 20)
            struct.pack_into('<I', payload, 20, 24)
            payload.extend(raw_entry)
            struct.pack_into('<I', payload, 4, len(payload))
            header = bytearray(20)
            header[:4] = b'FLAN'
            struct.pack_into('<HHIIHH', header, 4, 0xfeff, 20, 0x09000000, 20 + len(payload), 1, 0)
            return bytes(header + payload)
        before = archive(entry)
        old = T.P.parse_animation(before)['entries'][0]
        values = [{T.ROOT: {'translation_x': 20. + i, 'translation_y': -30.}} for i in range(33)]
        after = archive(T.rebuild(before, old, values))
        new = T.P.parse_animation(after)['entries'][0]
        for channel in old['channels']:
            if channel['tag'] == 'FLVI' or channel['property'] == 'translation_z':
                updated = next(c for c in new['channels'] if (c['tag'], c['target']) == (channel['tag'], channel['target']))
                self.assertEqual(T.blob(before, channel), T.blob(after, updated))
        x = next(c for c in new['channels'] if c['property'] == 'translation_x')
        self.assertEqual(T.P.eval_channel(x, 23), 43.)


if __name__ == '__main__':
    unittest.main()
