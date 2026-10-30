"""Read-only foreground conflict check; gamescope alone is not a running game."""
import json
import os
from pathlib import Path


def active_games(proc=Path('/proc')):
    found = []
    for path in proc.iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid():
            continue
        try:
            env = dict(item.split(b'=', 1) for item in (path/'environ').read_bytes().split(b'\0') if b'=' in item)
            app = env.get(b'SteamAppId', b'0')
            exe = str((path/'exe').readlink())
        except (OSError, ValueError):
            continue
        if app.isdigit() and int(app) != 0:
            found.append({'pid': int(path.name), 'appid': app.decode(), 'process': Path(exe).name})
    return found


if __name__ == '__main__':
    games = active_games()
    print(json.dumps({'idle_for_build': not games, 'active_game_processes': games}))
    raise SystemExit(1 if games else 0)
