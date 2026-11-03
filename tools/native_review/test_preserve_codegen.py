"""Reproduce stale legacy reuse and check mixed native/V8 link composition."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / 'ports/ultratears-linux/highfps/preserve_codegen.py'
spec = importlib.util.spec_from_file_location('preserve_codegen', MODULE)
codegen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codegen)


class CodegenTests(unittest.TestCase):
    def fixture(self, root):
        trusted = root / 'v8'
        trusted.mkdir()
        policy = root / 'overrides.json'
        files = {}
        recipes = ['rule cc_recovery', '  command = clang $recovery_clang_args -c $in -o $out']
        legacy = root / 'legacy'
        legacy.mkdir()
        objects = []
        self.sources = []
        for i in range(3):
            src = root / 'main' / f'main_{i:03}.c'
            src.parent.mkdir(exist_ok=True)
            src.write_text(f'void f{i}(void) {{}}')
            self.sources.append(src)
            obj = trusted / f'{i:04}_main_{i:03}.o'
            obj.write_bytes(b'correct-v8-object')
            old = legacy / obj.name
            old.write_bytes(b'wrong-but-existing-object')
            objects.append(str(old))
            files['main/' + src.name] = {'sha256': codegen.sha(src), 'extra_clang_args': ['-mllvm', '-disable-cgp']}
            recipes.extend([f'build {obj}: cc_recovery {src}', '  recovery_clang_args = -O1 -mllvm -disable-cgp'])
        policy.write_text(json.dumps({'files': files}))
        (trusted / 'ultratears').write_bytes(b'trusted-native-elf')
        (trusted / 'ultratears.build.json').write_text(json.dumps({
            'compile_overrides_sha256': codegen.sha(policy), 'compile_overrides_files': list(files),
            'binary_sha256': codegen.sha(trusted / 'ultratears')}))
        (trusted / 'build.ninja').write_text('\n'.join(recipes) + '\n')
        # Newest host features must survive selecting the older game-code set.
        host = root / 'gyro_decode.o'
        host.write_bytes(b'newest-gyro-and-input-runtime')
        objects.append(str(host))
        patched = root / 'patched.c'
        patched.write_text('void f1(void) { /* timing fix */ }')
        prep = {'chunks': [{'original': str(self.sources[1]), 'candidate': str(patched),
            'original_sha256': codegen.sha(self.sources[1]), 'candidate_sha256': codegen.sha(patched)}]}
        plan = f'rule link\n  command = cc $in -o $out\nbuild {root}/old-elf: link ' + ' '.join(objects) + '\n'
        return dict(text=plan, trusted=trusted, overrides=policy, prepared=prep, out=root / 'new', expected_chunks=3)

    def test_existing_legacy_objects_never_win_and_patched_chunk_inherits_flags(self):
        with tempfile.TemporaryDirectory(prefix='cgp-', dir=Path(__file__).parent) as temp:
            args = self.fixture(Path(temp))
            text, inventory = codegen.preserve_plan(**args)
            _, inputs = codegen.one_link(text)
            self.assertFalse(any('/legacy/' in p for p in inputs))
            self.assertIn(str(args['trusted'] / '0000_main_000.o'), inputs)
            self.assertIn(str(args['out'] / '0001_main_001.o'), inputs)
            self.assertIn(str(Path(temp) / 'gyro_decode.o'), inputs)
            self.assertIn('recovery_clang_args = -O1 -mllvm -disable-cgp', text)
            self.assertIn('rule cc_v8_candidate\n  command = clang $recovery_clang_args', text)
            self.assertEqual(inventory['numeric_chunks'], 3)
            self.assertEqual(inventory['recompiled_chunks'], ['main_001'])
            self.assertEqual(len(inventory['immutable_object_hashes']), 3)

    def test_subsequent_overlay_reuses_recovery_rule_without_duplicate(self):
        with tempfile.TemporaryDirectory(prefix='cgp-', dir=Path(__file__).parent) as temp:
            args = self.fixture(Path(temp))
            first, _ = codegen.preserve_plan(**args)
            # First build finished; the next overlay must keep the same contract.
            args['out'].mkdir()
            (args['out'] / '0001_main_001.o').write_bytes(b'patched-v8-object')
            args['text'] = first
            args['out'] = Path(temp) / 'next'
            second, _ = codegen.preserve_plan(**args)
            self.assertEqual(second.count('rule cc_v8_candidate\n'), 1)
            self.assertIn(str(args['out'] / '0001_main_001.o'), codegen.one_link(second)[1])

    def test_missing_workaround_is_rejected_even_when_objects_exist(self):
        with tempfile.TemporaryDirectory(prefix='cgp-', dir=Path(__file__).parent) as temp:
            args = self.fixture(Path(temp))
            plan = args['trusted'] / 'build.ninja'
            plan.write_text(plan.read_text().replace('-O1 -mllvm -disable-cgp', '-O1', 1))
            with self.assertRaisesRegex(ValueError, 'flags disagree'):
                codegen.preserve_plan(**args)

    def test_missing_chunk_or_modified_source_is_rejected(self):
        for scenario in ['link', 'source', 'object', 'candidate', 'baseline']:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix='cgp-', dir=Path(__file__).parent) as temp:
                args = self.fixture(Path(temp))
                if scenario == 'link':
                    args['text'] = args['text'].replace(str(Path(temp) / 'legacy/0002_main_002.o'), '')
                elif scenario == 'source':
                    self.sources[0].write_text('changed')
                elif scenario == 'object':
                    (args['trusted'] / '0000_main_000.o').unlink()
                elif scenario == 'candidate':
                    Path(args['prepared']['chunks'][0]['candidate']).write_text('changed')
                else:
                    (args['trusted'] / 'ultratears').write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    codegen.preserve_plan(**args)


if __name__ == '__main__':
    unittest.main()
