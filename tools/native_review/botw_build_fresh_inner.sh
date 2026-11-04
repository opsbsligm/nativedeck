#!/bin/bash
set -euo pipefail
work="${BOTW_FRESH_WORK:?Run botw_build_fresh.sh first}"
tool_dir="${BOTW_FRESH_TOOLS:?Missing public tool directory}"
source="$work/source"
export TMPDIR="$work/tmp"
prefix="$HOME/native-recomp/swr-src/build/linux/x86_64/deps"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
test -f "$prefix/include/SDL3/SDL.h"
pkg-config --modversion sdl3 libavformat
python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install --disable-pip-version-check -r "$tool_dir/botw-build-requirements.txt"
"$work/venv/bin/python" -m pip freeze > "$work/python-dependencies.txt"
cd "$source"
echo 'FRESH_GENERATION_START'
if [[ -f "$work/generation-seal.json" ]]; then
    "$work/venv/bin/python" "$tool_dir/botw_seal_generation.py" --work "$work" --check
else
    make B=build GEN=generated PY=../venv/bin/python GENARGS=--legacy-sdk7 gen
    echo 'FRESH_GENERATION_DONE'
    "$work/venv/bin/python" "$tool_dir/botw_seal_generation.py" --work "$work"
fi
echo 'FRESH_GENERATION_DONE'
echo 'FRESH_COMPILE_START'
make -j4 B=build GEN=generated PY=../venv/bin/python GENARGS=--legacy-sdk7 \
    LDFLAGS="-fuse-ld=lld -rdynamic -L$prefix/lib -lSDL3 -lavformat -lavcodec -lavutil -lswscale -lvulkan -lshaderc_shared -lz -lpthread -ldl -lm" \
    build/swgame.so
echo 'FRESH_COMPILE_DONE'
file build/savagewind build/swgame.so
sha256sum build/savagewind build/swgame.so
cat build/swgame.so.id
echo 'FRESH_BUILD_SUCCESS'
