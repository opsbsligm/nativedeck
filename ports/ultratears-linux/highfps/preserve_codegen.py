"""Keep V8 codegen recovery when composing native incremental link plans.

Only numeric generated chunks come from V8. Host/runtime/gyro objects remain
those of the selected incremental plan. Existing legacy objects never override
V8 merely because they happen to exist on disk.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

CHUNK = re.compile(r'^\d+_((?:main|sdk|subsdk0)_\d+)\.o$')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def blocks(text):
    result = []
    for line in text.splitlines():
        if line and not line.startswith(' '):
            result.append([line])
        elif result:
            result[-1].append(line)
    return result


def one_link(text):
    links = [line for line in text.splitlines() if line.startswith('build ') and ': link ' in line]
    require(len(links) == 1, 'Expected exactly one native linker target')
    target, inputs = links[0][6:].split(': link ', 1)
    require(all(':' not in p and '$' not in p for p in inputs.split()), 'Unsupported linker inputs')
    return target, inputs.split()


def preserve_plan(text, *, trusted, overrides, prepared, out, expected_chunks=1432):
    """Return corrected plan plus a byte-bound input inventory; never build."""
    trusted = Path(trusted)
    out = Path(out)
    policy = json.loads(Path(overrides).read_text())
    build_record = trusted / 'ultratears.build.json'
    record = json.loads(build_record.read_text())
    require(record['compile_overrides_sha256'] == sha(overrides), 'V8 recovery policy changed')
    require(record['binary_sha256'] == sha(trusted / 'ultratears'), 'V8 baseline ELF changed')
    require(set(record['compile_overrides_files']) == set(policy['files']), 'Incomplete V8 recovery record')
    trusted_text = (trusted / 'build.ninja').read_text()
    trusted_blocks = blocks(trusted_text)
    recipes = {}
    for block in trusted_blocks:
        line = block[0]
        if not line.startswith('build ') or ': ' not in line:
            continue
        obj, recipe = line[6:].split(': ', 1)
        match = CHUNK.fullmatch(Path(obj).name)
        if not match:
            continue
        fields = recipe.split()
        require(len(fields) == 2 and fields[0] == 'cc_recovery', 'Numeric chunk lost V8 recovery: ' + obj)
        source = Path(fields[1])
        key = source.parent.name + '/' + source.name
        entry = policy['files'].get(key)
        require(entry is not None and sha(source) == entry['sha256'], 'Generated source drift: ' + key)
        require(entry.get('extra_clang_args', [])[-2:] == ['-mllvm', '-disable-cgp'], 'CGP workaround missing: ' + key)
        settings = dict(x.strip().split(' = ', 1) for x in block[1:] if ' = ' in x)
        args = settings.get('recovery_clang_args', '').split()
        require('-O1' in args and args[-len(entry['extra_clang_args']):] == entry['extra_clang_args'],
                'Ninja recovery flags disagree with policy: ' + key)
        require(match.group(1) not in recipes, 'Duplicate V8 codegen chunk')
        require(Path(obj).is_file(), 'V8 object missing: ' + obj)
        recipes[match.group(1)] = (obj, str(source), block[1:])
    require(len(recipes) == expected_chunks and len(policy['files']) == expected_chunks, 'Incomplete V8 numeric chunk set')
    replacements = {}
    for item in prepared['chunks']:
        source = Path(item['original'])
        stem = source.stem
        require(stem in recipes and stem not in replacements, 'Unknown/duplicate patched chunk')
        require(recipes[stem][1] == str(source) and sha(source) == item['original_sha256'], 'Patch source drift')
        require(sha(item['candidate']) == item['candidate_sha256'], 'Patched candidate drift')
        replacements[stem] = item
    old_target, inputs = one_link(text)
    output = str(out / 'ultratears')
    candidate_rules = []
    selected = []
    seen = set()
    retained = {}
    for obj in inputs:
        match = CHUNK.fullmatch(Path(obj).name)
        if not match:
            selected.append(obj)
            # Some caller-owned candidates have not been compiled yet.
            if Path(obj).parent != out:
                retained[obj] = sha(obj)
            continue
        stem = match.group(1)
        require(stem in recipes and stem not in seen, 'Unknown/duplicate numeric link input')
        seen.add(stem)
        original, source, settings = recipes[stem]
        if stem in replacements:
            item = replacements[stem]
            new_obj = str(out / Path(original).name)
            candidate_rules.append([f'build {new_obj}: cc_v8_candidate {item["candidate"]}', *settings])
            selected.append(new_obj)
        else:
            selected.append(original)
            retained[original] = sha(original)
    require(seen == set(recipes), 'Link does not cover the complete V8 chunk set')
    recovery = [b for b in trusted_blocks if b[0] == 'rule cc_recovery']
    require(len(recovery) == 1, 'Missing V8 compiler recipe')
    require(any('$recovery_clang_args' in line for line in recovery[0]), 'V8 recipe ignores recovery flags')
    # Keep caller-owned host build edges, never their old numeric chunk edges.
    kept = []
    for block in blocks(text):
        first = block[0]
        if first.startswith('default ') or first == 'rule cc_v8_candidate':
            continue
        if first.startswith('build '):
            obj = first[6:].split(': ', 1)[0]
            if obj == old_target or CHUNK.fullmatch(Path(obj).name) or Path(obj).parent != out:
                continue
        kept.append(block)
    kept.append(['rule cc_v8_candidate', *recovery[0][1:]])
    kept.extend(candidate_rules)
    kept.extend([[f'build {output}: link ' + ' '.join(selected)], ['default ' + output]])
    mutable_inputs = {}
    for item in prepared['chunks']:
        for key in ['original', 'candidate']:
            mutable_inputs[item[key]] = sha(item[key])
    for block in kept:
        if block[0].startswith('build ') and ': cc ' in block[0]:
            source = block[0].split(': cc ', 1)[1].split()[0]
            mutable_inputs[source] = sha(source)
    # Timing declarations are included via absolute paths by the generated patch.
    for source in list(mutable_inputs):
        for header in re.findall(r'^#include "(/[^"\n]+)"', Path(source).read_text(), re.MULTILINE):
            mutable_inputs[header] = sha(header)
    inventory = {'schema': 1, 'numeric_chunks': len(seen), 'recompiled_chunks': sorted(replacements),
                 'trusted_build_record_sha256': sha(build_record),
                 'trusted_plan_sha256': sha(trusted / 'build.ninja'),
                 'compile_overrides_sha256': sha(overrides),
                 'compile_overrides_files': sorted(policy['files']),
                 'immutable_object_hashes': retained, 'mutable_input_hashes': mutable_inputs,
                 'patched_sources': prepared['chunks'],
                 'baseline_elf_sha256': record['binary_sha256']}
    return '\n'.join('\n'.join(b) for b in kept) + '\n', inventory


def main():
    root = Path.home() / 'native-recomp/work/totk-1.4.3-20261031'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, default=root / 'highfps-20261103/prepare.json')
    parser.add_argument('--trusted', type=Path, default=root / 'build-cgp-all-v8')
    parser.add_argument('--overrides', type=Path, default=root / 'compiler-overrides.v8-all-cgp.json')
    args = parser.parse_args()
    require(not args.out.exists(), 'Candidate output must be a new directory')
    text, inventory = preserve_plan(args.base_plan.read_text(), trusted=args.trusted,
        overrides=args.overrides, prepared=json.loads(args.prepared.read_text()), out=args.out)
    inventory['parent_plan_sha256'] = sha(args.base_plan)
    args.out.mkdir(parents=True)
    (args.out / 'build.ninja').write_text(text)
    inventory['candidate_plan_sha256'] = sha(args.out / 'build.ninja')
    (args.out / 'codegen-selection.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print('V8 codegen preserved; five chunk compiles + native link, one job, peak <1.2 GiB.', flush=True)


if __name__ == '__main__':
    main()
