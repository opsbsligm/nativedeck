#!/bin/bash
# BOTW 1.6.0 SDK7: native runtime, fixed save directory, guarded launch.
set -euo pipefail
ulimit -c 0
here="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec python3 "$here/botw_launch.py" --root "$here" "$@"
