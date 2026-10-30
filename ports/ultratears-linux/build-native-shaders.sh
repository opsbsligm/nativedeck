#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' '原生Linux shader translator：单CPU，nice19，CLR堆上限512MiB/进程，虚拟地址上限8GiB；项目额外磁盘预算500MiB'
exec distrobox enter -n nativedeck-build -- bash -lc '
set -euo pipefail
ulimit -c 0
ulimit -v 8388608
port_root=/home/deck/native-recomp/ports/ultratears-linux-20261030
export DOTNET_GCHeapHardLimit=20000000 DOTNET_GCConserveMemory=9 DOTNET_PROCESSOR_COUNT=1
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 MSBUILDDISABLENODEREUSE=1
export DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER=1
exec nice -n 19 taskset -c 0 python3 -u "$port_root/source/tools/build_xlate.py" --rid linux-x64 --dotnet "$port_root/deps/dotnet-10.0.403/dotnet" --out "$port_root/build/shaders" --cache "$port_root/deps/managed-cache" --jobs 1
'
