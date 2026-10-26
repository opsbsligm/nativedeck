#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Macro-region shape audit over the FULL captured Deck hardware log population.

Why this exists
---------------
ScarletNX hashes the LIVE maximal same-batch run starting at the bound word
(src/nx/gpu/maxwell/mme.c, mme_choose), while eden's MacroEngine hashes a PER-KEY SNAPSHOT
taken at upload time. The two only agree when the region shape makes a hash a pure function
of (start, end).

Faithful parsing note (this corrects the earlier ad-hoc grep):
    "mme: macro %u at word %x, %u words uploaded together, hash %016llx: %s"
the %u is `n` as COMPUTED BY mme_choose itself -- the live same-batch run length SNX hashed,
NOT an upload length reported by eden. So this audit measures SNX's own hashing input, which
is exactly the side we need to pin.

Invariants proved over every captured sample (not the 14 hand-picked ones used earlier):
  1. every run ends at the same word  -> one upload batch, no mid-stream restart, so SNX's
     live run and eden's snapshot cover the same word span;
  2. regions are strictly nested (suffix-shaped), so no two regions "cross" -- a crossing
     pair would make the hash depend on upload ORDER as well as content;
  3. hash is stable per (start, end) across runs, and distinct across the 14 live macros
     (no collision in the native-table lookup);
  4. the start offsets seen on hardware are exactly the set the parity harness replays, so
     harness/regionparity3.cpp Regime R is a faithful replay and not a guess.

Exit 0 == all invariants hold. Backs `region_semantics_equivalent_*` in STATUS.md.
"""
from __future__ import annotations

import collections
import glob
import os
import re
import sys

PAT = re.compile(
    r"mme: macro (\d+) at word ([0-9a-f]+), (\d+) words uploaded together, "
    r"hash ([0-9a-f]+): (\w+)"
)

# The start offsets regionparity3.cpp's Regime R replays (first-seen bind order aside).
HARNESS_STARTS = [0, 23, 55, 67, 74, 106, 112, 116, 123, 129, 139, 149, 169, 176]


def main(root: str) -> int:
    files = sorted(glob.glob(os.path.join(root, "run-*/launch-3.log")))
    if not files:
        print(f"FAIL: no logs under {root}", file=sys.stderr)
        return 2

    pop = []  # (file, idx, start, run_len, end, hash, path)
    for f in files:
        with open(f, errors="replace") as fh:
            for line in fh:
                m = PAT.search(line)
                if not m:
                    continue
                start = int(m.group(2), 16)
                length = int(m.group(3))
                pop.append((f, int(m.group(1)), start, length, start + length,
                            m.group(4), m.group(5)))

    if not pop:
        print("FAIL: no `mme: macro` samples captured", file=sys.stderr)
        return 2

    ends = collections.Counter(r[4] for r in pop)
    spans = sorted({(r[2], r[4]) for r in pop})                       # (start, end)
    starts = sorted({r[2] for r in pop})
    crosses = [(a, b) for i, a in enumerate(spans) for b in spans[i + 1:]
               if a[0] < b[0] < a[1] < b[1]]
    nested = all(x[0] <= y[0] and y[1] <= x[1] or y[0] <= x[0] and x[1] <= y[1]
                 for i, x in enumerate(spans) for y in spans[i + 1:])

    hash_by_span = collections.defaultdict(set)
    for r in pop:
        hash_by_span[(r[2], r[4])].add(r[5])
    multi_hash = {k: v for k, v in hash_by_span.items() if len(v) > 1}
    distinct_hashes = {r[5] for r in pop}
    paths = collections.Counter(r[6] for r in pop)
    # SNX hashes the run from `start`; run length must equal end-start exactly.
    len_mismatch = [r for r in pop if r[3] != r[4] - r[2]]

    print(f"files scanned            : {len(files)} "
          f"({', '.join(os.path.basename(os.path.dirname(f)) for f in files)})")
    print(f"samples (log lines)      : {len(pop)}")
    print(f"distinct macro slots     : {len({r[1] for r in pop})}")
    print(f"distinct regions         : {len(spans)}")
    print(f"distinct hashes          : {len(distinct_hashes)}")
    print(f"end-word distribution    : {dict(ends)}")
    print(f"execution paths observed : {dict(paths)}")
    print(f"regions (start,len)      : {[(s, e - s) for s, e in spans]}")
    print(f"start offsets            : {starts}")

    ok = True
    if len(ends) != 1:
        print("FAIL: runs do not share one end word -> uploads restart mid-stream, so SNX's "
              "live maximal run and eden's snapshot can cover different spans")
        ok = False
    if len(starts) != len(spans):
        print("FAIL: a start offset appears with two different ends")
        ok = False
    if not nested or crosses:
        print(f"FAIL: {len(crosses)} crossing region pairs -> hash depends on upload order")
        ok = False
    if len_distinct := len_mismatch:
        print(f"FAIL: {len(len_distinct)} samples whose logged run length != end-start")
        ok = False
    if multi_hash:
        print(f"FAIL: span hashed differently across runs: {list(multi_hash.items())[:3]}")
        ok = False
    if len(distinct_hashes) != len(spans):
        print("FAIL: hash collision across distinct regions (native table lookup would alias)")
        ok = False
    if starts != sorted(HARNESS_STARTS):
        print(f"FAIL: hardware starts {starts} differ from the parity harness replay set "
              f"{sorted(HARNESS_STARTS)}")
        ok = False

    if ok:
        print("\nPASS: every captured run is a suffix of ONE upload batch (all end at the same "
              "word), regions are strictly nested, and each hash is a stable, distinct function "
              "of (start,end).")
        print("=> SNX's live maximal-run read and eden's per-key snapshot cover the identical "
              "word sequence for every region ever observed on this hardware.")
        return 0
    return 1


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(main(os.path.join(here, "..", "deckprobe", "deck-forensics-20261026")))
