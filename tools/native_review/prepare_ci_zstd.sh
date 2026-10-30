#!/usr/bin/env bash
# Install only the public test dependency into the disposable job workspace.
set -euo pipefail
task_deps=$1
if command -v zstd >/dev/null 2>&1; then
  zstd --version
  exit 0
fi
mkdir -p "$task_deps/bin" "$task_deps/src"
archive="$task_deps/zstd-1.5.7.tar.gz"
echo '准备测试依赖zstd；预计工作区峰值64MiB'
python3 - "$archive" <<'PY'
import hashlib
import sys
import urllib.request
from pathlib import Path

target = Path(sys.argv[1])
url = 'https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz'
expected = 'eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3'
with urllib.request.urlopen(url, timeout=45) as stream:
    data = stream.read(8 * 1024 * 1024 + 1)
if len(data) > 8 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit('Unexpected zstd source archive')
target.write_bytes(data)
print('官方源码SHA-256已核对')
PY
tar -xzf "$archive" -C "$task_deps/src" --strip-components=1
make -C "$task_deps/src/programs" -j2 zstd
ln -sf "$task_deps/src/programs/zstd" "$task_deps/bin/zstd"
"$task_deps/bin/zstd" --version
