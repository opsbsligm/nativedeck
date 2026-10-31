# Public BC7 immutable-base / writable-overlay regression

GPL-3.0-or-later; see `LICENSE` and `SOURCES.md`. Offline, no ROM, assets,
keys, game installation, network, GPU, Python packages or external test framework.
Requirements: Python 3.8+ (without `-O` / `PYTHONOPTIMIZE`), `git`, and on Linux
`cc` with pthreads and Linux memfd/procfs support. Python standard library only.

From the repository root:

```sh
python3 -B -m unittest tools.native_review.test_bc7_overlay_native -v
python3 -B ports/ultratears-linux/cache-tests/run_tests.py
```

The existing `tools/native_review/test_*.py` unittest discovery picks up the
bridge automatically; CI configuration is unchanged. Linux must run all three
bridge tests with zero skips; a missing compiler, git, production patch, fixture,
SHA mismatch, compilation failure or native test failure fails the suite. macOS
runs the parse and production-binding/integrity tests and explicitly skips only
the native execution test. The standalone native command fails on non-Linux.
For portable checks alone:

```sh
python3 -B ports/ultratears-linux/cache-tests/run_tests.py --integrity-only
```

## Production binding

1. Verify `fixture/upstream/src/gfx/vkb_bc7.c` against its manifest SHA. This is
   the original GPL upstream source at commit
   `0c9ce8afd4c3ab81c33200917af51fb9807aeef0`, obtained with
   `git show HEAD:src/gfx/vkb_bc7.c` from the pinned replay checkout.
2. In an isolated empty git repository, apply the **actual sibling**
   `../linux.patch` using `git apply --check --include=src/gfx/vkb_bc7.c`, followed
   by `git apply --include=src/gfx/vkb_bc7.c`. Other production files are excluded.
3. Independently verify and apply `vkb_bc7.patch` to the post-Linux fixture at
   `fixture/src/gfx/vkb_bc7.c`. Verify both outputs against candidate SHA-256
   `aedc87dfb7d3e81675275dabd1c9ed8bcd7d8ab488c57861165ea73434e3b188`
   and compare their complete source text. There is no shipped second production C.
4. Compile the rebuilt source with dependency includes supplied by `shim.h` and
   entry points in `harness.c`; cache implementation bodies are unchanged.
   Real FILE I/O, mmap, pthreads, locks and background queue paths are exercised.
   Codec/key generation and selected platform dependencies are test shims;
   real BC7 encoding correctness and renderer integration are outside this suite.

All git operations ignore ambient `GIT_*`, user/system git configuration,
attributes and custom templates. No checkout, commit, remote or fetch is needed.
Source and patch drift fail before compilation. Updating a production BC7 hunk
requires intentional review/update of fixtures, independent patch and hashes.
Changes elsewhere in `linux.patch` do not affect this narrowly scoped binding.

## Counts and evidence

- **34 unique Linux native groups**: immutable base hashes; append/reload; queue;
  concurrency; mmap fallback; duplicate precedence; 14 corrupt base/delta cases;
  seven aliases; legacy/empty overlay; missing base/long path; two short-write
  cases; two cross-process locks. Full names are in `evidence/linux-validation.json`.
- **4 unique integrity checks**: reject fixture drift, patch drift, candidate SHA
  drift and non-applicable hunk (the last intentionally prints a git apply error).
- **3 unittest bridge tests**: Python AST parse; portable production binding plus
  all four integrity checks; Linux native suite. These are wrapper tests, not
  additional native cases. A bridge run repeats integrity checks in its native
  wrapper; do not count these as extra distinct cases.

`evidence/macos-validation.json` records local parse/binding/integrity verification;
`evidence/linux-validation.json` records Linux x86_64 validation in the existing
container as uid 65534, read-only package, all three bridge tests passing,
34 native groups and four integrity checks, with zero skips. Public files and
production patch were transported only through stdin. Container temporary files
used `/dev/shm/nativedeck-bc7-public-ci-*`, with `TMPDIR` underneath. A memfd copy
allows harness execution even on a noexec shared-memory mount; no executable is
installed. Temporary directories and descriptors were cleaned after completion.
No Deck project, game runtime, source tree or GitLab was written.

Optional `--json-out PATH` records a successful summary. Use a report directory;
all intermediate git repositories and synthetic cache files are task-named
TemporaryDirectories under `TMPDIR` and removed, including read-only fixtures.
This work created no local `/private/tmp` artifacts; the final tmp listing was
checked and evidence is archived here within the authorized delivery paths.

These are **synthetic native cache regressions**, not real-game acceptance.
`game_hardware_validated=false`; the main thread owns current in-game validation.

## Exact integration file list (16 added files)

```text
ports/ultratears-linux/cache-tests/LICENSE
ports/ultratears-linux/cache-tests/README.md
ports/ultratears-linux/cache-tests/SOURCES.md
ports/ultratears-linux/cache-tests/evidence/linux-validation.json
ports/ultratears-linux/cache-tests/evidence/macos-validation.json
ports/ultratears-linux/cache-tests/fixture/src/gfx/vkb_bc7.c
ports/ultratears-linux/cache-tests/fixture/upstream/src/gfx/vkb_bc7.c
ports/ultratears-linux/cache-tests/harness.c
ports/ultratears-linux/cache-tests/manifest.json
ports/ultratears-linux/cache-tests/production_binding.py
ports/ultratears-linux/cache-tests/run_tests.py
ports/ultratears-linux/cache-tests/shim.h
ports/ultratears-linux/cache-tests/test_cache.py
ports/ultratears-linux/cache-tests/test_integrity.py
ports/ultratears-linux/cache-tests/vkb_bc7.patch
tools/native_review/test_bc7_overlay_native.py
```
