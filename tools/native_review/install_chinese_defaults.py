"""Stage Chinese defaults for the next launch; never terminate the active game."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from chinese_font_check import inspect
from settings_defaults import apply


def install():
    root = Path.home()/'native-recomp'
    evidence = root/'evidence/review-20261030'
    swr = root/'swr'
    launcher = swr/'run.sh'
    old = launcher.read_bytes()
    if hashlib.sha256(old).hexdigest() != 'c447c820a837649d882db31726dde01e65f88281e37ad7b7c3352f269018a79b':
        raise ValueError('Launcher changed since review; refusing to replace it')
    font = evidence/'font-input/wqy-microhei.ttc'
    expected = '2420e8078af796b19a3f6ef13de527a1a91c1e7171eea115926c614ced1009b3'
    if hashlib.sha256(font.read_bytes()).hexdigest() != expected:
        raise ValueError('Unexpected font hash')
    check = inspect(font, swr/'games/botw-1.6.0/romfs/Pack/Bootup_CNzh.pack')
    if not check['coverage_passed']:
        raise ValueError('Font does not cover the actual game text')
    with (evidence/'run.sh.before-chinese').open('xb') as stream:
        stream.write(old)
    fonts = swr/'releases/sdk7-20261029/fonts'
    fonts.mkdir(exist_ok=False)
    for name in ['wqy-microhei.ttc', 'COPYRIGHT-wqy-microhei.txt']:
        src, dst = evidence/'font-input'/name, fonts/name
        shutil.copy2(src, dst)
        if dst.read_bytes() != src.read_bytes():
            raise ValueError('Font readback mismatch')
    helper = swr/'settings_defaults.py'
    if helper.exists():
        raise ValueError('Defaults helper already exists')
    shutil.copy2(Path(__file__).with_name('settings_defaults.py'), helper)
    if helper.read_bytes() != Path(__file__).with_name('settings_defaults.py').read_bytes():
        raise ValueError('Defaults helper readback mismatch')
    needle = 'unset SAVAGEWIND_ROMFS_OVERLAY\n'
    if old.decode().count(needle) != 1:
        raise ValueError('Unexpected launcher layout')
    text = old.decode().replace(needle, '''export SAVAGEWIND_FONT="${SAVAGEWIND_FONT:-$here/releases/sdk7-20261029/fonts/wqy-microhei.ttc}"
python3 "$here/settings_defaults.py"
unset SAVAGEWIND_ROMFS_OVERLAY
''')
    candidate = launcher.with_name('run.sh.chinese-new')
    with candidate.open('x') as stream:
        stream.write(text)
    candidate.chmod(launcher.stat().st_mode & 0o777)
    subprocess.run(['bash', '-n', str(candidate)], check=True)
    settings = Path.home()/'.local/share/savagewind/savagewind.ini'
    changed = apply(settings)
    candidate.replace(launcher)
    if launcher.read_text() != text:
        raise ValueError('Launcher readback mismatch')
    result = dict(check, defaults_configured=True, active_game_restarted=False,
                  settings_changed=changed, settings_sha256=hashlib.sha256(settings.read_bytes()).hexdigest(),
                  launcher_sha256=hashlib.sha256(launcher.read_bytes()).hexdigest(),
                  rollback_launcher=str(evidence/'run.sh.before-chinese'))
    with (evidence/'chinese-defaults-install.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    install()
