"""Close packaging error paths in the reviewed, already hardened TOTK wrapper.

This one-time migration accepts the precise intermediate launcher only. It
does not start a build or touch existing game output.
"""
import hashlib
import subprocess
from pathlib import Path


def transform(text):
    replacements = [
        ('set -uo pipefail', 'set -euo pipefail'),
        ('  local edge avail home gb', '  local edge avail home_gb root_mb'),
        ('  home=$(df', '  home_gb=$(df'),
        ('${home:-0}', '${home_gb:-0}'),
        ('${home}G', '${home_gb}G'),
        ('home=${home}G', 'home=${home_gb}G'),
        ('# ---- C5 三判据自动验收', '# ---- C5 原生构建静态检查（实机验收另行执行）'),
        ('say "原生三判据验收"', 'say "原生构建静态检查"'),
        ('静态重编译 -> ninja 编译链接 x86-64 原生 ELF -> 三判据自动验收',
         '静态重编译 -> ninja 编译链接 x86-64 原生 ELF -> 静态检查（非实机验收）'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    token = '  python3 "$ND/tools/native-review/check_game_idle.py" || return 1'
    if text.count(token) != 1:
        raise ValueError('Unexpected idle guard')
    text = text.replace(token, '''  root_mb=$(df -P -BM / | awk 'NR==2{gsub("M","",$4);print $4}')
  [ "${root_mb:-0}" -ge 400 ] || { echo "guard: rootfs available < 400MiB"; return 1; }
'''+token)
    start = text.index('distrobox enter "$BOX" -- bash ')
    end = text.index('[ $RC -eq 0 ]', start)
    invocation = text[start:text.index('\n', start)]
    text = text[:start] + 'if '+invocation+'; then RC=0; else RC=$?; fi\n' + text[end:]
    start = text.index('D="$OUT/dist/totk-recomp"; AR=')
    end = text.index('\ncat <<DONE', start)
    text = text[:start] + '''D="$OUT/dist/totk-recomp"
PACKAGE_ID="$(date +%Y%m%d-%H%M%S)-$$"
AR="$ND/dist/totk-recomp-x86_64-steamos-$PACKAGE_ID.tar.zst"
MANIFEST="$STAGE/dist-manifest-$PACKAGE_ID.sha256"
bash "$ND/tools/native-review/package_native_dir.sh" "$D" "$AR" "$MANIFEST" \\
  > "$STAGE/dist-archive-$PACKAGE_ID.sha256" \\
  || die "C6" "打包或读回校验失败，未交付归档" "原生静态检查" "$LOG"
''' + text[end:]
    text = text.replace('$STAGE/dist-manifest.sha256', '$MANIFEST')
    return text


def install():
    root = Path.home()/'native-recomp'
    evidence = root/'evidence/review-20261030'
    wrapper = root/'build-totk.sh'
    before = wrapper.read_bytes()
    if hashlib.sha256(before).hexdigest() != 'a681d3e1862b221edfe39ecd647207083727448ee8d9e872911902fe838f6b62':
        raise ValueError('Wrapper changed since review; refusing to replace')
    after = transform(before.decode())
    with (evidence/'build-totk.sh.before-packaging-fix').open('xb') as stream:
        stream.write(before)
    src = Path(__file__).with_name('package_native_dir.sh')
    dst = root/'tools/native-review/package_native_dir.sh'
    with dst.open('xb') as stream:
        stream.write(src.read_bytes())
    if src.read_bytes() != dst.read_bytes():
        raise ValueError('Packaging helper readback mismatch')
    candidate = wrapper.with_name('build-totk.sh.packaging-new')
    with candidate.open('x') as stream:
        stream.write(after)
    candidate.chmod(wrapper.stat().st_mode & 0o777)
    subprocess.run(['bash', '-n', str(candidate)], check=True)
    candidate.replace(wrapper)
    if wrapper.read_text() != after:
        raise ValueError('Wrapper readback mismatch')
    print('Packaging failure paths closed; SHA256 '+hashlib.sha256(wrapper.read_bytes()).hexdigest())


if __name__ == '__main__':
    install()
