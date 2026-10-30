"""Apply the source-only SDK7 generator extension to the private Deck checkout."""
import difflib
import shutil
import subprocess
from pathlib import Path


def prepare(source):
    source = Path(source)
    upstream = Path.home()/'native-recomp/swr-src'
    head = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if head != '4249c880bc6b09ad0207fc3f6e7595346f08d232':
        raise ValueError('Review the source extension against the new upstream first')
    original = (source/'tools/gen.py').read_text()
    expected = subprocess.check_output(['git', '-C', str(upstream), 'show', head+':tools/gen.py'], text=True)
    if original != expected:
        raise ValueError('Generator already modified; refusing to overwrite')
    text = original.replace('    if opts.no_sites:\n', '''    if getattr(opts, 'legacy_sdk7', False):
        from legacy_sdk7 import verify_main
        path = os.path.join(opts.input, 'main') if opts.name in ('layout', 'all') else opts.input
        try:
            return verify_main(path, base, nso.build_id)
        except ValueError as exc:
            raise game_sites.SiteError(str(exc)) from exc
    if opts.no_sites:
''', 1)
    text = text.replace("    ap.add_argument('--any-version', action='store_true')", "    ap.add_argument('--legacy-sdk7', action='store_true', help='exact local 1.6.0 profile; original pacing/menus')\n    ap.add_argument('--any-version', action='store_true')", 1)
    text = text.replace('    args = ap.parse_args()\n', '''    args = ap.parse_args()
    if args.legacy_sdk7 and (args.no_sites or args.any_version):
        ap.error('--legacy-sdk7 cannot be combined with --no-sites or --any-version')
''', 1)
    text = text.replace('            lay = layout.checked(exefs)\n', '''            lay = layout.checked(exefs)
            if args.legacy_sdk7:
                from legacy_sdk7 import verify_exefs
                try:
                    verify_exefs(exefs, [m[0] for m in lay])
                except ValueError as exc:
                    raise layout.LayoutError(str(exc)) from exc
''', 1)
    if text == original or '--legacy-sdk7' not in text:
        raise ValueError('Source extension failed')
    make = source/'Makefile'
    old_make = make.read_text()
    new_make = old_make.replace('GAMELIB_SRCS += tools/layout.py tools/game_sites.py',
                               'GAMELIB_SRCS += tools/layout.py tools/game_sites.py tools/legacy_sdk7.py')
    if new_make == old_make:
        raise ValueError('Could not include profile in the generated library cache identity')
    target = source/'tools/legacy_sdk7.py'
    if target.exists():
        raise ValueError('Profile already exists')
    shutil.copy2(Path(__file__).with_name('legacy_sdk7.py'), target)
    (source/'tools/gen.py').write_text(text)
    make.write_text(new_make)
    patch = ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                       fromfile='a/tools/gen.py', tofile='b/tools/gen.py'))
    patch += ''.join(difflib.unified_diff(old_make.splitlines(True), new_make.splitlines(True),
                                        fromfile='a/Makefile', tofile='b/Makefile'))
    evidence = Path.home()/'native-recomp/evidence/review-20261030/sdk7-codegen.patch'
    with evidence.open('x') as stream:
        stream.write(patch)
    print('SDK7 generation now checks all original module hashes and emits true version/build metadata')


if __name__ == '__main__':
    prepare(Path.home()/'native-recomp/swr-test/port-sdk7')
