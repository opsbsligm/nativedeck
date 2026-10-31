# License and provenance

Upstream: https://github.com/kuraeow/ultratears

Pinned source: https://github.com/kuraeow/ultratears/blob/0c9ce8afd4c3ab81c33200917af51fb9807aeef0/src/gfx/vkb_bc7.c

UltraTears is GPL-3.0-or-later, as declared in its pinned README License section.
The complete GPLv3 text is preserved verbatim in `LICENSE`. Original source
comments are retained. The regression scripts, shim, harness and derived patch
are also distributed under GPL-3.0-or-later.

- `fixture/upstream/src/gfx/vkb_bc7.c`: exact original upstream bytes, read via
  `git show HEAD:src/gfx/vkb_bc7.c` at the pinned commit, before Linux patches.
  SHA-256: `536c49d3dec157105fb240b4c8329abb027b5153d2618b7ee3af2e5066db38d2`.
- `fixture/src/gfx/vkb_bc7.c`: GPL upstream-derived post-Linux pre-overlay source
  from the existing public regression package; SHA-256
  `b95a7fe77f8315d2878d1774a6b821ccfa8854e26bcab1f44304a2b21b0161f1`.
- `vkb_bc7.patch`: independently applies the immutable-base/delta cache change to
  that post-Linux fixture; hash and resulting C hash are in `manifest.json`.
- `../linux.patch`: actual production patch, read at test time, never copied into
  this package or replaced by its independent regression patch. Its BC7 diff is
  applied to the original fixture and must produce the same candidate bytes.
- `harness.c`, `shim.h`, `run_tests.py`, `test_cache.py`, `test_integrity.py` and
  `LICENSE`: copied from the already prepared offline public test package.
  Runner additions bind production, offer portable integrity checks and support
  memory-backed execution from a noexec shared-memory scratch directory.
- `production_binding.py` and repository bridge
  `tools/native_review/test_bc7_overlay_native.py`: integration code for these
  public tests. Evidence files record synthetic test results only.

Fixtures contain public upstream engine/cache code, not game-derived source or
content. SHA binding preserves the distinction between original source,
post-Linux fixture and the reconstructed production implementation.
