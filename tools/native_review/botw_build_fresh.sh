#!/bin/bash
set -euo pipefail
ulimit -c 0
work="${BOTW_FRESH_WORK:-$HOME/native-recomp/work/botw-complete-20261030}"
evidence="${BOTW_FRESH_EVIDENCE:-$HOME/native-recomp/evidence/botw-complete-20261030}"
tool_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
test -d "$work/source"
test -d "$evidence"
exec >>"$evidence/fresh-build.log" 2>&1
echo "Expected peak additional disk: <=25 GiB in native-recomp/work; memory capped at 10 GiB, CPU 4 cores."
if pgrep -x savagewind >/dev/null; then
    echo 'Game is running; refusing heavy build.'
    exit 1
fi
available=$(df --output=avail -B1 "$work" | tail -1)
if ((available < 35*1024*1024*1024)); then
    echo 'Not enough build space.'
    exit 1
fi
mkdir -p "$work/tmp"
export TMPDIR="$work/tmp"
export BOTW_FRESH_WORK="$work"
export BOTW_FRESH_EVIDENCE="$evidence"
export BOTW_FRESH_TOOLS="$tool_dir"
# This project-owned build container deliberately keeps these conservative caps.
# `podman update --memory=0 --cpus=0` does not remove limits on this host.
podman update --memory=10g --cpus=4 nativedeck-build
limits=$(podman exec nativedeck-build cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpu.max)
if [[ "$limits" != $'10737418240\n400000 100000' ]]; then
    echo 'Container build limits did not apply; refusing compilation.'
    exit 1
fi
distrobox enter nativedeck-build -- bash "$tool_dir/botw_build_fresh_inner.sh"
