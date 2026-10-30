"""Set the requested launch defaults while preserving explicit player settings.

Only missing/auto text language is changed to CNzh. Existing bindings, audio,
graphics and saves are not rewritten. A byte-for-byte backup precedes changes.
"""
import hashlib
import os
import re
import tempfile
from pathlib import Path


def apply(path):
    path = path.resolve()
    before = path.read_bytes() if path.exists() else b''
    text = before.decode('utf-8')
    rules = {'text_language': 'CNzh', 'button_icons': 'xbox'}
    for key, default in rules.items():
        pattern = re.compile(r'(?m)^[ \t]*'+key+r'[ \t]*=[ \t]*([^\r\n]*)(?:\r?\n|$)')
        matches = list(pattern.finditer(text))
        if len(matches) > 1:
            raise ValueError('Duplicate setting: '+key)
        if not matches:
            text += ('' if not text or text.endswith('\n') else '\n') + f'{key} = {default}\n'
        elif key == 'text_language' and matches[0].group(1).strip() in ('', 'auto'):
            text = pattern.sub(f'{key} = {default}\n', text, count=1)
    after = text.encode('utf-8')
    if after == before:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    backups = path.parent / 'native-settings-backups'
    backups.mkdir(exist_ok=True)
    backup = backups / (hashlib.sha256(before).hexdigest()+'.ini')
    if backup.exists():
        if backup.read_bytes() != before:
            raise ValueError('Backup checksum conflict')
    else:
        with backup.open('xb') as stream:
            stream.write(before)
    if hashlib.sha256(backup.read_bytes()).digest() != hashlib.sha256(before).digest():
        raise ValueError('Backup verification failed')
    fd, name = tempfile.mkstemp(prefix='.native-settings-', dir=path.parent)
    candidate = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after)
        if path.exists() and path.read_bytes() != before:
            raise ValueError('Settings changed concurrently; refusing to overwrite')
        if path.exists():
            candidate.chmod(path.stat().st_mode & 0o777)
        candidate.replace(path)
        if path.read_bytes() != after:
            raise ValueError('Settings readback failed')
    finally:
        candidate.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    home = Path.home()
    root = Path(os.environ.get('SAVAGEWIND_DATA_ROOT') or
                str(Path(os.environ.get('XDG_DATA_HOME') or str(home/'.local/share'))/'savagewind'))
    settings = Path(os.environ.get('SAVAGEWIND_SETTINGS') or 'savagewind.ini')
    apply(settings if settings.is_absolute() else root/settings)
