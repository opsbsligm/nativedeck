"""无需网络或游戏材料的编译恢复接口测试。

放置于 tools/native_review/test_ultratears_compile_recovery.py，自动从仓库内
ports/ultratears-linux/overlay/tools 导入现有 builder 和 linux_inputs。
临时人工单元写入本文件旁的任务命名目录，测试结束自动清理。
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
TOOLS = (Path(__file__).resolve().parents[2]
         / 'ports' / 'ultratears-linux' / 'overlay' / 'tools')
sys.path.insert(0, str(TOOLS))
import linux_inputs


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = import_file('ultratears_compile_recovery_build', TOOLS / 'build_linux.py')


class CompileOverrides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix='compiler-recovery-tests-',
                                                  dir=Path(__file__).resolve().parent)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.scratch.name)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.generated = self.root / 'generated'
        self.sources = []
        for relative in ('main/main_table.c', 'main/main_7.c', 'main/main_8.c', 'sdk/sdk_9.c'):
            source = self.generated / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b'/* synthetic public unit */\n')
            self.sources.append(source)
        (self.root/'runtime.c').write_bytes(b'int runtime_fixture;\n')
        (self.root/'runtime.cpp').write_bytes(b'int cxx_fixture;\n')
        self.config = self.root / 'overrides.json'
        self.out = self.root / 'out'
        self.exefs = self.root / 'not-read-exefs'
        self.document = {'schema': 1, 'kind': 'ultratears-compile-overrides',
                         'files': {'main/main_7.c': self.entry(self.sources[1])}}
        self.save()

    def entry(self, path):
        return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'extra_clang_args': ['-mllvm', '-enable-misched=false', '-mllvm', '-regalloc=fast']}

    def save(self):
        self.config.write_text(json.dumps(self.document))

    def load(self):
        return build.load_compile_overrides(self.config, self.generated, self.sources)

    def invoke(self, module=build, overrides=False, generate_only=True,
               target='game', verify_error=None):
        argv = ['build_linux.py', '--target', target, '--out', str(self.out),
                '--generated', str(self.generated), '--exefs', str(self.exefs), '--jobs', '2']
        if overrides:
            argv += ['--compile-overrides', str(self.config)]
        if generate_only:
            argv += ['--generate-only']
        output, error = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(module, 'ROOT', self.root))
            stack.enter_context(patch.object(module, 'source_lists', return_value=['runtime.c', 'runtime.cpp']))
            verify = stack.enter_context(patch.object(module, 'verify_generated',
                                                       return_value=self.sources, side_effect=verify_error))
            pkg = stack.enter_context(patch.object(module, 'pkg_flags',
                                                    return_value=['-I/synthetic/include', '-lfixture']))
            stack.enter_context(patch.object(module.shutil, 'which', side_effect=lambda tool: '/synthetic/bin/'+tool))
            stack.enter_context(patch.object(module.platform, 'machine', return_value='x86_64'))
            stack.enter_context(patch.object(sys, 'platform', 'linux'))
            stack.enter_context(patch.object(sys, 'argv', argv))
            ninja = stack.enter_context(patch.object(module.subprocess, 'call', return_value=0))
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(contextlib.redirect_stderr(error))
            try:
                module.main()
            except SystemExit as e:
                if e.code != 0:
                    return e.code, output.getvalue(), error.getvalue(), verify, ninja, pkg
        return 0, output.getvalue(), error.getvalue(), verify, ninja, pkg

    def test_verified_chunk_and_exact_config_fingerprint(self):
        selected, fingerprint = self.load()
        self.assertEqual(selected, {self.sources[1]: ('-mllvm', '-enable-misched=false', '-mllvm', '-regalloc=fast')})
        self.assertEqual(fingerprint, hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.config.write_text(self.config.read_text()+'\n')
        self.assertNotEqual(fingerprint, self.load()[1])

    def test_arbitrary_valid_chunk_names_not_hardcoded_crash_units(self):
        self.document['files'] = {'sdk/sdk_9.c': self.entry(self.sources[3]),
                                  'main/main_8.c': self.entry(self.sources[2])}
        self.save()
        self.assertEqual(set(self.load()[0]), {self.sources[2], self.sources[3]})

    def test_invalid_paths_runtime_tables_and_mismatched_modules(self):
        entry = self.entry(self.sources[1])
        for name in ('../main_7.c', '/main/main_7.c', 'main/../main/main_7.c',
                     'main/main_table.c', 'src/runtime.c', 'main/sdk_7.c',
                     'unknown/unknown_7.c', 'main/main_7.cpp', 'main\\main_7.c',
                     'main/main_7.c\n', 'main//main_7.c', './main/main_7.c'):
            with self.subTest(name=name):
                self.document['files'] = {name: entry}
                self.save()
                with self.assertRaisesRegex(ValueError, 'relative generated module/chunk'):
                    self.load()

    def test_flags_exact_whitelist(self):
        for flags in ([], ['-mllvm', '-enable-misched=false'], ['-mllvm', '-regalloc=fast'], ['-O2'], ['-O0', '-mllvm', '-regalloc=fast'], ['-mllvm'], ['-enable-misched=false', '-mllvm'],
                      ['-mllvm', '-enable-misched=true'],
                      ['-mllvm', '-enable-misched=false', '-O0'],
                      ['-mllvm', '-enable-misched=false; touch injected'],
                      ['@response'], '-mllvm -enable-misched=false', None):
            with self.subTest(flags=flags):
                self.document['files']['main/main_7.c']['extra_clang_args'] = flags
                self.save()
                with self.assertRaisesRegex(ValueError, 'arguments'):
                    self.load()

    def test_hash_format_and_content_mismatch(self):
        for digest in ('0'*64, 'x'*64, 'a'*63, 'a'*65, None, 123):
            with self.subTest(digest=digest):
                self.document['files']['main/main_7.c']['sha256'] = digest
                self.save()
                with self.assertRaises(ValueError):
                    self.load()

    def test_each_exact_allowed_recipe_still_requires_matching_source_sha(self):
        recipes = (['-mllvm', '-disable-cgp'],
                   ['-mllvm', '-enable-misched=false', '-mllvm', '-regalloc=fast'],
                   ['-O0'])
        for recipe in recipes:
            with self.subTest(recipe=recipe):
                self.document['files']['main/main_7.c'] = {**self.entry(self.sources[1]),
                                                           'extra_clang_args': recipe}
                self.save()
                selected, _ = self.load()
                self.assertEqual(selected[self.sources[1]], tuple(recipe))
                self.document['files']['main/main_7.c']['sha256'] = '0'*64
                self.save()
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    self.load()

    def test_O0_is_separate_and_machine_recipes_keep_O1(self):
        for recipe, expected in ((['-O0'], '-O0'),
                                 (['-mllvm', '-disable-cgp'], '-O1 -mllvm -disable-cgp'),
                                 (['-mllvm', '-enable-misched=false', '-mllvm', '-regalloc=fast'],
                                  '-O1 -mllvm -enable-misched=false -mllvm -regalloc=fast')):
            with self.subTest(recipe=recipe):
                self.document['files']['main/main_7.c']['extra_clang_args'] = recipe
                self.save()
                code, output, _, _, _, _ = self.invoke(overrides=True)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output)['compile_overrides_experimental'], recipe == ['-O0'])
                text = (self.out/'build.ninja').read_text()
                start = text.index('rule cc_recovery\n')
                end = text.index('build ', start)
                self.assertNotIn('-O1', text[start:end])
                self.assertNotIn('-O0', text[start:end])
                assignments = [line for line in text.splitlines()
                               if line.startswith('  recovery_clang_args = ')]
                self.assertEqual(assignments, ['  recovery_clang_args = '+expected])

    def test_changed_source_rejected(self):
        self.sources[1].write_bytes(b'/* changed same public fixture */\n')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.load()

    def test_source_must_be_in_verified_generated_list(self):
        self.sources.remove(self.sources[1])
        with self.assertRaisesRegex(ValueError, 'verified generated'):
            self.load()

    def test_missing_source_rejected(self):
        self.sources[1].unlink()
        with self.assertRaisesRegex(ValueError, 'regular non-symlink'):
            self.load()

    def test_source_symlink_inside_and_outside_generated_rejected(self):
        for destination in (self.sources[2], self.root/'runtime.c'):
            with self.subTest(destination=destination.name):
                self.sources[1].unlink()
                self.sources[1].symlink_to(destination)
                with self.assertRaisesRegex(ValueError, 'non-symlink'):
                    self.load()
                self.sources[1].unlink()
                self.sources[1].write_bytes(b'/* synthetic public unit */\n')

    def test_module_directory_symlink_rejected(self):
        moved = self.generated/'moved-main'
        (self.generated/'main').rename(moved)
        (self.generated/'main').symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            self.load()

    def test_generated_root_symlink_rejected(self):
        link = self.root/'generated-link'
        link.symlink_to(self.generated, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            build.load_compile_overrides(self.config, link, self.sources)

    def test_generated_root_symlink_ancestor_rejected(self):
        link = self.root/'parent-link'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            build.load_compile_overrides(self.config, link/'generated', self.sources)

    def test_config_symlink_and_duplicate_json_keys_rejected(self):
        link = self.root/'config-link'
        link.symlink_to(self.config)
        with self.assertRaises(ValueError):
            build.load_compile_overrides(link, self.generated, self.sources)
        for raw in ('{"schema":1,"schema":1}',
                    '{"files":{"main/main_7.c":{},"main/main_7.c":{}}}',
                    '{"entry":{"sha256":"a","sha256":"b"}}'):
            with self.subTest(raw=raw):
                self.config.write_text(raw)
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    self.load()

    def test_schema_and_extra_fields_are_strict(self):
        for doc in ([], {}, {**self.document, 'schema': True},
                    {**self.document, 'schema': 2}, {**self.document, 'kind': 'other'},
                    {**self.document, 'files': []}, {**self.document, 'extra': 1},
                    {**self.document, 'files': {'main/main_7.c': {**self.entry(self.sources[1]), 'extra': 1}}}):
            with self.subTest(doc=doc):
                self.config.write_text(json.dumps(doc))
                with self.assertRaises(ValueError):
                    self.load()

    def test_existing_verifier_import_retained_and_failure_precedes_output(self):
        self.assertIs(build.verify_generated, linux_inputs.verify_generated)
        code, _, err, verify, ninja, pkg = self.invoke(overrides=True, verify_error=ValueError('manifest failed'))
        self.assertEqual(code, 2)
        self.assertIn('manifest failed', err)
        verify.assert_called_once_with(self.generated, self.exefs)
        pkg.assert_not_called()
        ninja.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_runtime_override_rejected(self):
        code, _, err, verify, ninja, _ = self.invoke(overrides=True, target='runtime')
        self.assertEqual(code, 2)
        self.assertIn('requires --target game', err)
        verify.assert_not_called()
        ninja.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_bad_override_precedes_output_and_ninja(self):
        self.document['files']['main/main_7.c']['sha256'] = '0'*64
        self.save()
        code, _, err, verify, ninja, pkg = self.invoke(overrides=True)
        self.assertEqual(code, 2)
        self.assertIn('SHA-256 mismatch', err)
        verify.assert_called_once_with(self.generated, self.exefs)
        ninja.assert_not_called()
        pkg.assert_not_called()
        self.assertFalse(self.out.exists())


    def test_only_selected_edge_changes_other_commands_byte_identical(self):
        self.assertEqual(self.invoke()[0], 0)
        original = (self.out/'build.ninja').read_text()
        version_mtime = (self.out/'version.h').stat().st_mtime_ns
        code, output, _, verify, ninja, _ = self.invoke(overrides=True)
        self.assertEqual(code, 0)
        verify.assert_called_once_with(self.generated, self.exefs)
        ninja.assert_not_called()
        candidate = (self.out/'build.ninja').read_text()
        start = candidate.index('rule cc_recovery\n')
        end = candidate.index('build ', start)
        recovery_rule = candidate[start:end]
        self.assertIn('$recovery_clang_args', recovery_rule)
        self.assertIn('  recovery_clang_args = -O1 -mllvm -enable-misched=false -mllvm -regalloc=fast\n', candidate)
        restored = candidate[:start] + candidate[end:]
        # Compare against this builder with overrides disabled; only the selected edge may differ.
        self.assertEqual(restored.count(': cc_recovery '), 1)
        self.assertIn('0003_main_7.o: cc_recovery ', restored)
        restored = ''.join(line for line in restored.splitlines(keepends=True)
                           if not line.startswith('  recovery_clang_args = '))
        self.assertEqual(restored.replace(': cc_recovery ', ': cc '), original)
        self.assertEqual((self.out/'version.h').stat().st_mtime_ns, version_mtime)
        record = json.loads(output)
        self.assertEqual(record['compile_overrides_sha256'], hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertEqual(record['compile_overrides_files'], ['main/main_7.c'])
        self.assertFalse(record['game_playability_validated'])
        self.assertFalse(record['compile_overrides_experimental'])

    def test_multiple_selected_units_keep_original_numbering_and_other_rules(self):
        self.document['files']['sdk/sdk_9.c'] = {**self.entry(self.sources[3]),
                                                   'extra_clang_args': ['-O0']}
        self.save()
        self.assertEqual(self.invoke()[0], 0)
        original = (self.out/'build.ninja').read_text()
        self.assertEqual(self.invoke(overrides=True)[0], 0)
        candidate = (self.out/'build.ninja').read_text()
        start = candidate.index('rule cc_recovery\n')
        end = candidate.index('build ', start)
        restored = candidate[:start]+candidate[end:]
        self.assertEqual(restored.count(': cc_recovery '), 2)
        self.assertIn('0003_main_7.o: cc_recovery ', restored)
        self.assertIn('0005_sdk_9.o: cc_recovery ', restored)
        restored = ''.join(line for line in restored.splitlines(keepends=True)
                           if not line.startswith('  recovery_clang_args = '))
        self.assertEqual(restored.replace(': cc_recovery ', ': cc '), original)

    def test_tmpdir_child_only_and_local_directory(self):
        old_environment = dict(os.environ)
        code, output, _, _, ninja, _ = self.invoke(overrides=True, generate_only=False)
        self.assertEqual(code, 0)
        ninja.assert_called_once()
        self.assertEqual(ninja.call_args.args[0], ['ninja', '-f', str(self.out/'build.ninja'), '-j', '2', '-k', '0'])
        child_env = ninja.call_args.kwargs['env']
        self.assertEqual(child_env['TMPDIR'], str(self.out/'tmp'))
        self.assertEqual({k:v for k,v in child_env.items() if k != 'TMPDIR'},
                         {k:v for k,v in old_environment.items() if k != 'TMPDIR'})
        self.assertEqual(dict(os.environ), old_environment)
        self.assertTrue((self.out/'tmp').is_dir())
        self.assertEqual(json.loads(output)['ninja_tmpdir'], str(self.out/'tmp'))

    def test_symlink_tmpdir_rejected_before_ninja(self):
        self.out.mkdir()
        (self.out/'tmp').symlink_to(self.root, target_is_directory=True)
        code, _, err, _, ninja, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn('out/tmp must not be a symlink', err)
        ninja.assert_not_called()

    def test_empty_override_is_noop_with_fingerprint(self):
        self.document['files'] = {}
        self.save()
        self.assertEqual(self.invoke()[0], 0)
        original = (self.out/'build.ninja').read_bytes()
        code, output, _, _, _, _ = self.invoke(overrides=True)
        self.assertEqual(code, 0)
        self.assertEqual((self.out/'build.ninja').read_bytes(), original)
        self.assertEqual(json.loads(output)['compile_overrides_files'], [])
        self.assertIsNotNone(json.loads(output)['compile_overrides_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
