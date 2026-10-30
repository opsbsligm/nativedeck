"""Launch the installed SDK7 BOTW without changing or interrupting a running game."""
import argparse
import fcntl
import hashlib
import json
import os
import selectors
import shutil
import signal
import stat
import string
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from settings_defaults import apply

MAX_SAVE_BYTES = 128 * 1024 * 1024
CONSOLE_BYTES = 1024 * 1024


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.status-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def running_games(proc_root=Path('/proc')):
    """Also detect games started by the previous launcher, before locks existed."""
    result = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            name = os.readlink(entry/'exe').removesuffix(' (deleted)')
            if Path(name).name == 'savagewind':
                result.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError as exc:
            # Portals and other non-dumpable user services can deny /exe readlink.
            # Their public comm/cmdline still distinguish them from Savage Wind.
            try:
                comm = (entry/'comm').read_text().strip()
                argv0 = (entry/'cmdline').read_bytes().split(b'\0', 1)[0].decode(errors='replace')
                if comm == 'savagewind' or Path(argv0).name == 'savagewind':
                    result.append(int(entry.name))
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError:
                raise RuntimeError('无法确认游戏是否空闲，保留当前会话') from exc
    return sorted(result)


def acquire_lock(path):
    # Never unlink a lock file: replacing its inode would let a second launcher in.
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(fd, 'r+')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        return None
    return stream


def save_inventory(root):
    if root.is_symlink():
        raise ValueError('存档根目录不能是符号链接')
    if not root.exists():
        return {}
    if not root.is_dir():
        raise ValueError('存档路径不是目录')
    result, total = {}, 0
    def fail_walk(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=fail_walk):
        for name in dirs:
            if (Path(directory)/name).is_symlink():
                raise ValueError('存档目录含符号链接')
        for name in sorted(files):
            path = Path(directory)/name
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('存档目录含非普通文件')
            total += before.st_size
            if total > MAX_SAVE_BYTES or len(result) >= 4096:
                raise ValueError('存档超过备份上限，未启动游戏')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(block)
            after = path.lstat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('存档仍在变化，未启动游戏')
            result[path.relative_to(root).as_posix()] = {'size': before.st_size, 'sha256': digest.hexdigest()}
    return dict(sorted(result.items()))


def backup_saves(source, destination):
    """Copy only while idle, verify both sides, then publish an immutable snapshot."""
    inventory = save_inventory(source)
    if not inventory:
        return {'snapshot': None, 'files': 0}
    digest = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination/digest
    if target.exists():
        if save_inventory(target/'save') != inventory:
            raise ValueError('已有存档备份校验失败，保留原文件')
        return {'snapshot': digest, 'files': len(inventory), 'reused': True}
    if shutil.disk_usage(destination).free < sum(v['size'] for v in inventory.values()) + 256*1024*1024:
        raise ValueError('存档备份空间不足，未启动游戏')
    stage = Path(tempfile.mkdtemp(prefix='.snapshot-', dir=destination))
    try:
        (stage/'save').mkdir(mode=0o700)
        for name in inventory:
            out = stage/'save'/name
            out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(source/name, out)
            out.chmod(0o600)
            with out.open('rb') as stream:
                os.fsync(stream.fileno())
        if save_inventory(stage/'save') != inventory or save_inventory(source) != inventory:
            raise ValueError('存档备份或源文件并发校验失败，未启动游戏')
        atomic_json(stage/'manifest.json', {'files': inventory, 'created_at': datetime.now(timezone.utc).isoformat()})
        stage.rename(target)
        return {'snapshot': digest, 'files': len(inventory), 'reused': False}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def native_header(path):
    with path.open('rb') as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', header, 18)[0] != 62:
        raise ValueError('程序或游戏库不是原生Linux x86-64 ELF')


def preflight(root):
    root = root.resolve()
    descriptor = root/'native-active.json'
    profile = None
    if descriptor.exists():
        profile = json.loads(descriptor.read_text())
        if not isinstance(profile, dict) or profile.get('schema') != 1 or profile.get('version') != '1.6.0':
            raise ValueError('未知原生安装配置版本')
        def local_path(key):
            value = profile.get(key)
            if not isinstance(value, str) or Path(value).is_absolute() or '..' in Path(value).parts:
                raise ValueError('原生安装路径必须位于本游戏目录内')
            path = (root/value).resolve()
            if not path.is_relative_to(root):
                raise ValueError('原生安装路径越出本游戏目录')
            return path
        release = local_path('release')
        game = local_path('game')
        expected_id = profile.get('gamelib_id', '')
        if not isinstance(expected_id, str) or len(expected_id) != 16 or any(c not in string.digits+'abcdef' for c in expected_id):
            raise ValueError('无效游戏库版本标识')
    else:
        release = root/'releases/sdk7-20261029'
        game = root/'games/botw-1.6.0'
        expected_id = 'f0cd698371c0a703'
    runtime = release/'bin/savagewind'
    font = release/'fonts/wqy-microhei.ttc'
    for path in [runtime,game/'swgame.so',font,game/'swgame.so.id',game/'romfs',game/'exefs',game/'aoc1',game/'aoc2']:
        if not path.resolve().is_relative_to(root):
            raise ValueError('安装文件路径越出本游戏目录')
    native_header(runtime)
    native_header(game/'swgame.so')
    if not os.access(runtime, os.X_OK):
        raise ValueError('原生游戏程序缺少执行权限')
    if (game/'romfs/System/Version.txt').read_text().strip() != '1.6.0':
        raise ValueError('当前SDK7游戏目录要求1.6.0资源')
    if (game/'swgame.so.id').read_text().strip() != expected_id:
        raise ValueError('游戏库版本标识不匹配')
    for path in [font, game/'romfs/Pack/Bootup_CNzh.pack']:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('中文字体或简中资源缺失')
    if profile is not None:
        for name, path in [('runtime_sha256', runtime), ('gamelib_sha256', game/'swgame.so')]:
            expected = profile.get(name, '')
            if not isinstance(expected, str) or len(expected) != 64 or any(c not in string.digits+'abcdef' for c in expected):
                raise ValueError('缺少原生构建文件摘要')
            digest = hashlib.sha256()
            before = path.stat()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(block)
            after = path.stat()
            if digest.hexdigest() != expected or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('原生程序或游戏库校验失败')
        if profile.get('dlc') != {'1': '3.0', '2': '3.0'}:
            raise ValueError('完整安装必须同时登记两个3.0版DLC')
        for index in (1, 2):
            if (game/f'aoc{index}/System/AocVersion.txt').read_text().strip() != '3.0':
                raise ValueError('DLC内容缺失或版本不匹配')
        if 'ui' in profile:
            ui=profile['ui']
            if not isinstance(ui,dict) or ui.get('controller')!='steamdeck':
                raise ValueError('未知手柄示意图配置')
            bootup=game/'romfs/Pack/Bootup.pack'
            if not bootup.resolve().is_relative_to(game) or hashlib.sha256(bootup.read_bytes()).hexdigest()!=ui.get('bootup_sha256'):
                raise ValueError('Steam Deck示意图与指示线资源不匹配')
    return runtime, game, font


def write_console(path, chunk):
    if path.exists() and path.stat().st_size + len(chunk) > CONSOLE_BYTES:
        path.replace(path.with_suffix('.log.1'))
    with path.open('ab') as stream:
        stream.write(chunk)


def supervise(command, cwd, env, lock_fd, console):
    """Keep the lock through the child lifetime and forward Steam's stop signal."""
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True, pass_fds=(lock_fd,))
    old = {}
    def forward(signum, _frame):
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        old[sig] = signal.signal(sig, forward)
    selector = selectors.DefaultSelector()
    try:
        selector.register(child.stdout, selectors.EVENT_READ)
        ended = None
        while True:
            for key, _ in selector.select(timeout=0.2):
                block = os.read(key.fileobj.fileno(), 65536)
                if block:
                    write_console(console, block)
                else:
                    selector.unregister(key.fileobj)
            rc = child.poll()
            if rc is not None:
                ended = time.monotonic() if ended is None else ended
                if not selector.get_map() or time.monotonic()-ended > 1:
                    return rc if rc >= 0 else 128-rc
    except BaseException:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise
    finally:
        selector.close()
        child.stdout.close()
        for sig, handler in old.items():
            signal.signal(sig, handler)


def launch(root, args, data_root):
    state = data_root/'native-launch'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = acquire_lock(state/'instance.lock')
    if lock is None:
        print('旷野之息已经启动，本次未创建第二个实例。')
        return 0
    with lock:
        status = {'started_at': datetime.now(timezone.utc).isoformat(), 'phase': 'preflight'}
        try:
            pids = running_games()
            if pids:
                print('旷野之息仍在运行，保留当前会话：'+','.join(map(str, pids)))
                return 0
            runtime, game, font = preflight(root)
            status['save_backup'] = backup_saves(data_root/'save', state/'save-backups')
            settings = Path(os.environ.get('SAVAGEWIND_SETTINGS') or 'savagewind.ini')
            apply(settings if settings.is_absolute() else data_root/settings)
            env = os.environ.copy()
            env['SAVAGEWIND_DATA_ROOT'] = str(data_root)
            env['SAVAGEWIND_FONT'] = str(font)
            env['SAVAGEWIND_CC'] = str(root.parent/'tools/swr_cc.sh')
            env['LD_LIBRARY_PATH'] = str(runtime.parent.parent/'lib') + (
                ':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
            env['DISPLAY'] = env.get('DISPLAY') or ':0'
            env.pop('SAVAGEWIND_ROMFS_OVERLAY', None)
            if (root/'input-audit.enabled').is_file():
                # Use the runtime's existing GetNpadState trace, with real input enabled.
                # An empty script supplies no synthetic game actions.
                env['SAVAGEWIND_INPUT'] = ''
                env['SAVAGEWIND_NO_USER_INPUT'] = '0'
            status['phase'] = 'running'
            atomic_json(state/'last-launch.json', status)
            rc = supervise([str(runtime), '--play', str(game), *args], data_root, env, lock.fileno(), state/'console.log')
            status.update(phase='exited', exit_code=rc)
        except (OSError, ValueError, RuntimeError) as exc:
            status.update(phase='failed', error=str(exc), exit_code=1)
            print('旷野之息启动失败：'+str(exc), file=sys.stderr)
            rc = 1
        atomic_json(state/'last-launch.json', status)
        return rc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    options, game_args = parser.parse_known_args()
    xdg = os.environ.get('XDG_DATA_HOME', '')
    default = Path(xdg) if xdg.startswith('/') else Path.home()/'.local/share'
    data = Path(os.environ.get('SAVAGEWIND_DATA_ROOT') or str(default/'savagewind')).expanduser().resolve()
    raise SystemExit(launch(options.root.resolve(), game_args, data))
