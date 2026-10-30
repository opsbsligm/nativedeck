"""Keep real builds separate from probe output and add the native code check."""
import hashlib
import shutil
import subprocess
from pathlib import Path


def harden():
    root = Path.home()/'native-recomp'
    evidence = root/'evidence/review-20261030'
    path = root/'build-totk.sh'
    old = path.read_bytes()
    text = old.decode()
    required = ['OUT="$ND/totkbuild"', 'cat > "$ND/probe/m3-inner.sh" <<INNER',
                'LDD=$(env -i /usr/bin/ldd "$BIN" 2>&1)']
    if any(text.count(token) != 1 for token in required):
        raise ValueError('Build wrapper changed; refusing to overwrite')
    target = root/'tools/native-review'
    target.mkdir(exist_ok=True)
    for name in ['native_binary_check.py', 'check_game_idle.py', 'totk_build_inner.sh']:
        src, dst = Path(__file__).with_name(name), target/name
        if dst.exists():
            raise ValueError('Helper already exists: '+name)
        shutil.copy2(src, dst)
        if dst.read_bytes() != src.read_bytes():
            raise ValueError('Helper readback mismatch')
    text = text.replace('OUT="$ND/totkbuild"', 'OUT="$ND/totkbuild-real"')
    text = text.replace('  pgrep -x gamescope >/dev/null && { echo "guard: gamescope 前台在跑，排队不抢占"; return 1; }',
                        '  python3 "$ND/tools/native-review/check_game_idle.py" || return 1')
    start = text.index('cat > "$ND/probe/m3-inner.sh" <<INNER')
    end = text.index('say "容器内构建', start)
    text = text[:start] + '# Paths are passed as arguments, never interpolated into a shell program.\n' + text[end:]
    call = 'distrobox enter "$BOX" -- bash "$ND/probe/m3-inner.sh" > "$LOG" 2>&1'
    if text.count(call) != 1:
        raise ValueError('Unexpected container invocation')
    text = text.replace(call, 'distrobox enter "$BOX" -- bash "$ND/tools/native-review/totk_build_inner.sh" "$SRC" "$XCI" "$KEYS" "$OUT" "$GENOPT" "$SKIPEXTRACT" > "$LOG" 2>&1')
    needle = 'LDD=$(env -i /usr/bin/ldd "$BIN" 2>&1)'
    replacement = '''python3 "$ND/tools/native-review/native_binary_check.py" "$BIN" --totk > "$STAGE/totk-native-check.json" \\
  || die "C5" "游戏函数表为空或无法验证（运行时探针不能作为游戏产物）" "构建" "$LOG"
LDD=$(env -i LD_LIBRARY_PATH="$(dirname "$BIN")/lib" /usr/bin/ldd "$BIN" 2>&1) \\
  || die "C5" "动态依赖检查失败" "原生静态检查" "$LOG"
if echo "$LDD" | grep -q 'not found'; then die "C5" "运行依赖缺失" "原生静态检查" "$LOG"; fi'''
    text = text.replace(needle, replacement)
    text = text.replace('== 构建完成 ==', '== 构建产物已生成，实机验收仍待完成 ==')
    with (evidence/'build-totk.sh.before-review').open('xb') as stream:
        stream.write(old)
    candidate = path.with_name('build-totk.sh.review-new')
    with candidate.open('x') as stream:
        stream.write(text)
    candidate.chmod(path.stat().st_mode & 0o777)
    subprocess.run(['bash', '-n', str(candidate)], check=True)
    candidate.replace(path)
    if path.read_text() != text:
        raise ValueError('Build wrapper readback mismatch')
    print('Build wrapper hardened; SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    harden()
