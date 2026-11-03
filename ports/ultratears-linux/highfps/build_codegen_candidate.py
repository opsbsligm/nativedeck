"""Build a fresh recovered-codegen candidate and bind the ELF to exact inputs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import resource
import shutil
import subprocess

from preserve_codegen import require, sha


def input_inventory(candidate):
    candidate = Path(candidate)
    selection_path = candidate / 'codegen-selection.json'
    selection = json.loads(selection_path.read_text())
    plan = candidate / 'build.ninja'
    require(sha(plan) == selection['candidate_plan_sha256'], 'Candidate plan changed')
    inputs = {**selection['immutable_object_hashes'], **selection['mutable_input_hashes'],
              str(selection_path): sha(selection_path), str(plan): sha(plan)}
    for path, expected in inputs.items():
        require(sha(path) == expected, 'Build input changed: ' + path)
    return inputs


def verify_receipt(candidate):
    candidate = Path(candidate)
    receipt = json.loads((candidate / 'build-receipt.json').read_text())
    require(receipt.get('kind') == 'v8-incremental-build', 'Missing bound V8 build receipt')
    require(input_inventory(candidate) == receipt['inputs'], 'Selection or build inputs changed since compile')
    require(sha(candidate / 'ultratears') == receipt['binary_sha256'], 'Candidate ELF changed since compile')
    return receipt


def build(candidate, runner=subprocess.run):
    candidate = Path(candidate)
    require(not (candidate / 'ultratears').exists() and not (candidate / 'build-receipt.json').exists(),
            'Candidate output already exists; reconcile or use a fresh output directory')
    require(shutil.disk_usage(candidate).free > 3 * 1024**3, 'Insufficient bounded compile space')
    inputs = input_inventory(candidate)
    print('Five chunks + native link; peak <1.2 GiB, one compiler, 4 GiB address limit.', flush=True)
    with (candidate / 'build.log').open('x') as log:
        runner(['distrobox', 'enter', '-n', 'nativedeck-build', '--', 'nice', '-n', '19',
                'ninja', '-j1', '-f', str(candidate / 'build.ninja'), str(candidate / 'ultratears')],
               stdout=log, stderr=subprocess.STDOUT, check=True)
    require(input_inventory(candidate) == inputs, 'Inputs changed during compilation')
    receipt = {'kind': 'v8-incremental-build', 'at': datetime.now().astimezone().isoformat(),
               'inputs': inputs, 'binary_sha256': sha(candidate / 'ultratears')}
    with (candidate / 'build-receipt.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    verify_receipt(candidate)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    print(json.dumps({'binary_sha256': build(args.candidate)['binary_sha256']}))


if __name__ == '__main__':
    main()
