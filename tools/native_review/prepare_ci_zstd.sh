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
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

target = Path(sys.argv[1])
release_hash = 'eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3'
sources = []
job_token = os.environ.get('CI_JOB_TOKEN')
if os.environ.get('CI_PROJECT_ID') == '16' and job_token:
    sources.append(('https://gitlab.example.com:8445/api/v4/projects/16/packages/generic/'
                    'native-build-deps/1.5.7/zstd-1.5.7.tar.gz', release_hash, {'JOB-TOKEN': job_token}))
sources.extend([
    ('https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz', release_hash, {}),
    ('https://codeload.github.com/facebook/zstd/tar.gz/refs/tags/v1.5.7',
     '43636afda6dfd987be8612635866eaadd9cd4bb7fb4f175580dd71278a1266df', {}),
])
data = None
for url, expected, headers in sources:
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=45) as stream:
                candidate = stream.read(8 * 1024 * 1024 + 1)
        except (OSError, urllib.error.URLError) as error:
            print('zstd source unavailable:', type(error).__name__, 'attempt', attempt+1, flush=True)
            if attempt == 0: time.sleep(2)
            continue
        if len(candidate) > 8 * 1024 * 1024 or hashlib.sha256(candidate).hexdigest() != expected:
            raise SystemExit('Unexpected zstd source archive')
        data = candidate
        break
    if data is not None: break
if data is None: raise SystemExit('No verified zstd source available')
target.write_bytes(data)
print('官方源码SHA-256已核对')
PY
tar -xzf "$archive" -C "$task_deps/src" --strip-components=1
make -C "$task_deps/src/programs" -j2 zstd
ln -sf "$task_deps/src/programs/zstd" "$task_deps/bin/zstd"
"$task_deps/bin/zstd" --version
