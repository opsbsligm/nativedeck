import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import botw_launch as launch


class BotwLauncher(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd()/'.native-review-test-tmp'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.tmp.name)
        self.save = self.root/'data/save'
        self.save.mkdir(parents=True)
        (self.save/'slot').mkdir()
        (self.save/'slot/game_data.sav').write_bytes(b'original-save')
        self.backups = self.root/'backups'

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_snapshot_roundtrip_dedupe_and_corruption_refusal(self):
        before = launch.save_inventory(self.save)
        result = launch.backup_saves(self.save, self.backups)
        backup = self.backups/result['snapshot']/'save'
        self.assertEqual(before, launch.save_inventory(backup))
        self.assertTrue(launch.backup_saves(self.save, self.backups)['reused'])
        (backup/'slot/game_data.sav').write_bytes(b'damaged-backup')
        with self.assertRaisesRegex(ValueError, '备份校验失败'):
            launch.backup_saves(self.save, self.backups)
        self.assertEqual(before, launch.save_inventory(self.save))

    def test_source_change_during_backup_never_publishes_snapshot(self):
        original = launch.shutil.copy2
        def mutate(src, dst):
            original(src, dst)
            Path(src).write_bytes(b'changed-during-copy')
        with mock.patch.object(launch.shutil, 'copy2', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, '并发校验失败'):
                launch.backup_saves(self.save, self.backups)
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_symlink_escape_and_oversized_save_refused(self):
        (self.save/'escape').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, '符号链接'):
            launch.backup_saves(self.save, self.backups)
        (self.save/'escape').unlink()
        with mock.patch.object(launch, 'MAX_SAVE_BYTES', 1):
            with self.assertRaisesRegex(ValueError, '超过备份上限'):
                launch.backup_saves(self.save, self.backups)

    def test_unreadable_save_tree_is_not_silently_omitted(self):
        def blocked_walk(root, **kwargs):
            kwargs['onerror'](PermissionError('unreadable save directory'))
        with mock.patch.object(launch.os, 'walk', side_effect=blocked_walk):
            with self.assertRaises(PermissionError):
                launch.backup_saves(self.save, self.backups)
        self.assertFalse(self.backups.exists())

    def test_lock_blocks_other_process_and_releases_on_close(self):
        path = self.root/'lock'
        with launch.acquire_lock(path):
            script = ('import sys;from pathlib import Path;from botw_launch import acquire_lock;'
                      'sys.exit(0 if acquire_lock(Path(sys.argv[1])) is None else 1)')
            subprocess.run([sys.executable, '-c', script, str(path.resolve())],
                           cwd=Path(launch.__file__).parent, check=True)
        with launch.acquire_lock(path) as lock:
            self.assertIsNotNone(lock)

    def test_existing_prelock_game_and_deleted_exe_detected(self):
        proc = self.root/'proc'
        for pid, exe in [(101, '/native/savagewind'), (102, '/old/savagewind (deleted)'), (103, '/bin/python')]:
            (proc/str(pid)).mkdir(parents=True)
            (proc/str(pid)/'exe').symlink_to(exe)
        self.assertEqual(launch.running_games(proc), [101, 102])

    def test_live_game_does_not_touch_settings_or_saves(self):
        settings = self.save.parent/'savagewind.ini'
        settings.write_text('text_language = auto\n')
        before = launch.save_inventory(self.save)
        with mock.patch.object(launch, 'running_games', return_value=[113473]), \
             mock.patch.object(launch, 'preflight') as preflight:
            self.assertEqual(launch.launch(self.root/'missing-install', [], self.save.parent), 0)
        preflight.assert_not_called()
        self.assertEqual(settings.read_text(), 'text_language = auto\n')
        self.assertEqual(launch.save_inventory(self.save), before)
        self.assertFalse((self.save.parent/'native-launch/save-backups').exists())

    def test_restricted_portal_is_not_a_game_but_restricted_game_still_detected(self):
        proc = self.root/'proc'
        for pid, name in [(101, 'xdg-desktop-portal'), (102, 'savagewind')]:
            entry = proc/str(pid)
            entry.mkdir(parents=True)
            (entry/'comm').write_text(name+'\n')
            (entry/'cmdline').write_bytes(('/native/'+name+'\0').encode())
        with mock.patch.object(launch.os, 'readlink', side_effect=PermissionError):
            self.assertEqual(launch.running_games(proc), [102])

    def test_missing_install_records_error_without_mutating_save(self):
        before = launch.save_inventory(self.save)
        with mock.patch.object(launch, 'running_games', return_value=[]):
            self.assertEqual(launch.launch(self.root/'absent', [], self.save.parent), 1)
        status = json.loads((self.save.parent/'native-launch/last-launch.json').read_text())
        self.assertEqual(status['phase'], 'failed')
        self.assertEqual(launch.save_inventory(self.save), before)

    def test_wrong_arch_rejected(self):
        path = self.root/'aarch64.so'
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, 183)
        path.write_bytes(header)
        with self.assertRaisesRegex(ValueError, 'x86-64'):
            launch.native_header(path)

    def test_native_launch_uses_fixed_data_root_backups_and_reports_exit(self):
        runtime, game, font = self.root/'runtime', self.root/'game', self.root/'font'
        with mock.patch.object(launch, 'running_games', return_value=[]), \
             mock.patch.object(launch, 'preflight', return_value=(runtime, game, font)), \
             mock.patch.object(launch, 'supervise', return_value=17) as supervise:
            self.assertEqual(launch.launch(self.root, ['--example'], self.save.parent), 17)
        args = supervise.call_args.args
        self.assertEqual(args[0], [str(runtime), '--play', str(game), '--example'])
        self.assertEqual(args[1], self.save.parent)
        self.assertEqual(args[2]['SAVAGEWIND_DATA_ROOT'], str(self.save.parent))
        self.assertNotIn('SAVAGEWIND_ROMFS_OVERLAY', args[2])
        status = json.loads((self.save.parent/'native-launch/last-launch.json').read_text())
        self.assertEqual(status['exit_code'], 17)
        snapshot = self.save.parent/'native-launch/save-backups'/status['save_backup']['snapshot']/'save'
        self.assertEqual(launch.save_inventory(snapshot), launch.save_inventory(self.save))

    def test_supervisor_captures_errors_and_propagates_exit(self):
        console = self.root/'console.log'
        with launch.acquire_lock(self.root/'lock') as lock:
            rc = launch.supervise([sys.executable, '-c', 'import sys;print("failure evidence",file=sys.stderr);sys.exit(23)'],
                                  self.root, os.environ.copy(), lock.fileno(), console)
        self.assertEqual(rc, 23)
        self.assertIn(b'failure evidence', console.read_bytes())

    def test_supervisor_forwards_stop_and_preserves_child_lock(self):
        ready = self.root/'ready'
        child = self.root/'child'
        lock_path = self.root/'lock'
        code = ('import os,signal,time;from pathlib import Path;'
                'Path('+repr(str(child.resolve()))+').write_text(str(os.getpid()));'
                'signal.signal(signal.SIGTERM,lambda *a:exit(42));'
                'Path('+repr(str(ready.resolve()))+').touch();time.sleep(20)')
        script = ('from pathlib import Path;import os,sys;from botw_launch import acquire_lock,supervise;'
                  'lock=acquire_lock(Path(sys.argv[1]));'
                  'sys.exit(supervise([sys.executable,"-c",sys.argv[2]],Path.cwd(),os.environ.copy(),lock.fileno(),Path(sys.argv[3])))')
        proc = subprocess.Popen([sys.executable, '-c', script, str(lock_path.resolve()), code, str((self.root/'log').resolve())],
                                cwd=Path(launch.__file__).parent)
        try:
            deadline = time.monotonic()+8
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready.exists())
            self.assertIsNone(launch.acquire_lock(lock_path))
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=5), 42)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(child.read_text()), 0)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    def test_console_rotates_with_bounded_storage(self):
        path = self.root/'console.log'
        with mock.patch.object(launch, 'CONSOLE_BYTES', 12):
            launch.write_console(path, b'12345678')
            launch.write_console(path, b'abcdefgh')
        self.assertEqual(path.read_bytes(), b'abcdefgh')
        self.assertEqual(path.with_suffix('.log.1').read_bytes(), b'12345678')


if __name__ == '__main__':
    unittest.main()
