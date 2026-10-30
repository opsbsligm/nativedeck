#!/usr/bin/env bash
set -euo pipefail
src=$1
xci=$2
keys=$3
out=$4
opt=$5
skip=$6
export CC=clang CXX=clang++
cd "$src"
args=("$xci" "$keys" --out "$out" --jobs 4 --gen-jobs 3 --gen-opt "$opt")
if [[ "$skip" == 1 ]]; then
  args+=(--skip-extract)
fi
exec bash tools/build_from_xci.sh "${args[@]}"
