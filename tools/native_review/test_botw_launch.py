import json
import hashlib
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

    def active_fixture(self):
        release=self.root/'releases/fresh'
        game=self.root/'games/fresh'
        dummy_id=format(42,'016x')
        header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',header,18,62)
        for path in [release/'bin/savagewind',game/'swgame.so']:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(header);path.chmod(0o755)
        for path,value in [(release/'fonts/wqy-microhei.ttc',b'font'),(game/'romfs/Pack/Bootup_CNzh.pack',b'pack'),
                           (game/'romfs/System/Version.txt',b'1.6.0'),(game/'swgame.so.id',dummy_id.encode()),
                           (game/'aoc1/System/AocVersion.txt',b'3.0'),(game/'aoc2/System/AocVersion.txt',b'3.0')]:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        profile={'schema':1,'version':'1.6.0','release':'releases/fresh','game':'games/fresh',
                 'gamelib_id':dummy_id,'runtime_sha256':hashlib.sha256(header).hexdigest(),
                 'gamelib_sha256':hashlib.sha256(header).hexdigest(),'dlc':{'1':'3.0','2':'3.0'}}
        (self.root/'native-active.json').write_text(json.dumps(profile))
        return release,game,profile

    def test_new_build_profile_checks_actual_binaries_and_both_dlcs(self):
        release,game,_=self.active_fixture()
        self.assertEqual(launch.preflight(self.root)[:2],(release/'bin/savagewind',game))
        (game/'swgame.so').write_bytes((game/'swgame.so').read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'校验失败'):
            launch.preflight(self.root)

    def test_profile_path_escape_and_symlink_escape_are_refused(self):
        _,_,profile=self.active_fixture()
        for path in ['../outside','/tmp/other-game']:
            profile['release']=path
            (self.root/'native-active.json').write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError,'路径'):
                launch.preflight(self.root)
        (self.root/'escape').symlink_to(self.root.parent)
        profile['release']='escape'
        (self.root/'native-active.json').write_text(json.dumps(profile))
        with self.assertRaisesRegex(ValueError,'路径'):
            launch.preflight(self.root)

    def test_missing_second_dlc_refuses_full_profile(self):
        _,game,_=self.active_fixture()
        (game/'aoc2/System/AocVersion.txt').write_text('2.0')
        with self.assertRaisesRegex(ValueError,'DLC内容'):
            launch.preflight(self.root)

    def test_profile_array_and_nested_file_escape_are_refused(self):
        release,game,profile=self.active_fixture()
        (self.root/'native-active.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'配置版本'):
            launch.preflight(self.root)
        (self.root/'native-active.json').write_text(json.dumps(profile))
        (release/'bin/savagewind').unlink()
        (release/'bin/savagewind').symlink_to(self.root.parent/'outside-runtime')
        with self.assertRaisesRegex(ValueError,'路径'):
            launch.preflight(self.root)

    def test_steamdeck_diagram_requires_matching_layout_pack(self):
        _,game,profile=self.active_fixture()
        pack=game/'romfs/Pack/Bootup.pack'
        pack.write_bytes(b'private-layout-fixture')
        profile['ui']={'controller':'steamdeck','bootup_sha256':hashlib.sha256(pack.read_bytes()).hexdigest()}
        (self.root/'native-active.json').write_text(json.dumps(profile))
        launch.preflight(self.root)
        pack.write_bytes(b'different-callout-layout')
        with self.assertRaisesRegex(ValueError,'指示线资源'):
            launch.preflight(self.root)

    def test_input_audit_enables_existing_trace_without_disabling_real_controller(self):
        (self.root/'input-audit.enabled').touch()
        with mock.patch.object(launch,'running_games',return_value=[]), \
             mock.patch.object(launch,'preflight',return_value=(self.root/'bin/savagewind',self.root/'game',self.root/'font')), \
             mock.patch.object(launch,'supervise',return_value=0) as supervise:
            self.assertEqual(launch.launch(self.root,[],self.save.parent),0)
        env=supervise.call_args.args[2]
        self.assertEqual(env['SAVAGEWIND_INPUT'],'')
        self.assertEqual(env['SAVAGEWIND_NO_USER_INPUT'],'0')


if __name__ == '__main__':
    unittest.main()
