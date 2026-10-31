# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the public cache regression to the repository's actual Linux patch."""
import os
from pathlib import Path
import shutil
import subprocess


def rebuild_production(package, work, manifest, require_sha):
    source = package / manifest['production_fixture']
    require_sha(source.read_bytes(), manifest['production_fixture_sha256'], 'original upstream fixture')
    patch = (package / manifest['production_patch']).resolve(strict=True)
    target = work / 'src/gfx/vkb_bc7.c'
    target.parent.mkdir(parents=True)
    shutil.copyfile(str(source), str(target))
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    base = ['git', '-c', 'core.attributesFile=' + os.devnull]
    subprocess.run(base + ['init', '--quiet', '--template=', str(work)], env=env, check=True, timeout=30)
    for options in (['--check'], []):
        subprocess.run(base + ['-C', str(work), 'apply'] + options +
                       ['--include=src/gfx/vkb_bc7.c', str(patch)], env=env, check=True, timeout=30)
    candidate = target.read_bytes()
    require_sha(candidate, manifest['candidate_sha256'], 'actual production linux.patch result')
    return candidate.decode('utf-8')
