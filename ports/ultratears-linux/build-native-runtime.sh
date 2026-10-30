#!/usr/bin/env bash
set -euo pipefail
port_root="$HOME/native-recomp/ports/ultratears-linux-20261030"
echo 'Linux运行时代码编译：预计磁盘峰值250MiB；并行1，低优先级，单进程地址空间上限2GiB'
exec distrobox enter -n nativedeck-build -- bash -lc '
set -euo pipefail
ulimit -v 2097152
export PKG_CONFIG_PATH="/home/deck/native-recomp/totkbuild/deps/sdl3-install/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export ULTRS_VULKAN_INCLUDE="/home/deck/native-recomp/totkbuild/deps/vulkan-headers/include"
exec nice -n 19 python3 -u /home/deck/native-recomp/ports/ultratears-linux-20261030/source/tools/build_linux.py --target runtime --out /home/deck/native-recomp/ports/ultratears-linux-20261030/build --jobs 1
'
