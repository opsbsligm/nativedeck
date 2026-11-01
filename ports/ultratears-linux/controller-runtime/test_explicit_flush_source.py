#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict checks against the actual sequentially replayed production sources.

Usage: python3 -B test_explicit_flush_source.py --source /isolated/replay
No game input, renderer start, device access or source modification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import unittest

SOURCE = None
ART = Path(__file__).resolve().parent


def body(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    for i in range(brace + 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[brace + 1:i]
    raise ValueError('Unbalanced function: ' + signature)


class ExplicitFlushSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SOURCE is None:
            raise RuntimeError('Supply --source with the fully replayed production source')
        cls.text = {name: (SOURCE / name).read_text() for name in (
            'src/gfx/nvn/hle_nvn.c', 'src/gfx/nvn/nvn_dirty.h',
            'src/gfx/nvn/nvn_dirty_win.c', 'src/gfx/nvn/totk_vpool_win.c', 'src/gfx/vkb_tex.c')}
        cls.tracker = cls.text['src/gfx/nvn/nvn_dirty_win.c']
        cls.tex = cls.text['src/gfx/vkb_tex.c']
        cls.hle = cls.text['src/gfx/nvn/hle_nvn.c']

    def test_public_api_declarations(self):
        header = self.text['src/gfx/nvn/nvn_dirty.h']
        for declaration in ('int nvn_dirty_mark_range(const void *addr, size_t len);',
                            'int nvn_dirty_marked_since(const void *addr, size_t len, uint64_t stamp);',
                            'uint64_t nvn_dirty_notice_epoch(void);'):
            self.assertEqual(header.count(declaration), 1)

    def test_mark_range_checks_and_positive_notice(self):
        mark = body(self.tracker, 'int nvn_dirty_mark_range(')
        for token in ('if (!len) return 0;', 'len > UINTPTR_MAX - a', 'a + len > r->end',
                      'pthread_mutex_lock(&g_slot_mu)', 'atomic_store(&r->gen[p], generation)',
                      'atomic_fetch_add_explicit(&g_notice_epoch, 1, memory_order_release)'):
            self.assertIn(token, mark)
        self.assertLess(mark.index('UINTPTR_MAX - a'), mark.index('find(a)'))
        self.assertLess(mark.index('atomic_store(&r->gen[p]'), mark.index('&g_notice_epoch'))

    def test_marked_since_unknown_is_not_clean(self):
        query = body(self.tracker, 'int nvn_dirty_marked_since(')
        self.assertIn('return -1;', query)
        self.assertIn('atomic_load(&r->gen[p]) > stamp', query)
        self.assertIn('pthread_mutex_lock(&g_slot_mu)', query)
        self.assertIn('memory_order_acquire', body(self.tracker, 'uint64_t nvn_dirty_notice_epoch('))

    def test_three_explicit_flush_entrypoints(self):
        for signature in ('NVN(nvnMemoryPoolFlushMappedRange,', 'NVN(nvnBufferFlushMappedRange,',
                          'NVN(nvnTextureFlushTexels,'):
            self.assertEqual(body(self.hle, signature).count('nvn_dirty_mark_range('), 1)
        buffer = body(self.hle, 'NVN(nvnBufferFlushMappedRange,')
        self.assertLess(buffer.index('dm_guest_write_prepare('), buffer.index('nvn_dirty_mark_range('))

    def test_pool_texture_bounds_are_subtraction_based(self):
        pool = body(self.hle, 'NVN(nvnMemoryPoolFlushMappedRange,')
        texture = body(self.hle, 'NVN(nvnTextureFlushTexels,')
        self.assertIn('n > o->size - (uint64_t)off', pool)
        self.assertIn("MAGIC('P','O','O','L')", pool)
        self.assertIn('o->L.size > o->pool->size - (uint64_t)o->off', texture)
        self.assertIn("MAGIC('T','E','X',0)", texture)
        self.assertIn('nvn_dirty_mark_range(o->mem, (size_t)o->L.size)', texture)

    def test_same_submission_notice_rechecks(self):
        stale = body(self.tex, 'int vkb_tex_stale(')
        self.assertIn('image_entry->notice_checked, __ATOMIC_ACQUIRE) != notice', stale)
        self.assertIn('im->dirty_checked == sub && image_entry->notice_checked == notice', stale)
        self.assertIn('int pending_notice = im->stale;', stale)
        self.assertIn('(pending_notice || image_entry->notice_checked != notice)', stale)

    def test_sampled_epoch_published_after_query(self):
        stale = body(self.tex, 'int vkb_tex_stale(')
        sample = stale.index('uint64_t notice = nvn_dirty_notice_epoch();')
        query = stale.index('nvn_dirty_marked_since(')
        publish = stale.index('__atomic_store_n(&image_entry->notice_checked, notice, __ATOMIC_RELEASE)')
        self.assertLess(sample, query)
        self.assertLess(query, publish)
        self.assertEqual(stale.count('nvn_dirty_notice_epoch()'), 1)

    def test_virtual_and_aside_paths_have_notices(self):
        virtual = body(self.text['src/gfx/nvn/totk_vpool_win.c'], 'int totk_vpool_dirty_since(')
        self.assertIn('nvn_dirty_marked_since(cpu, n, stamp) > 0', virtual)
        self.assertIn('nvn_dirty_marked_since(e->im.storage, L.size, e->released_stamp) > 0', self.tex)
        self.assertIn('im->gpu_written', body(self.tex, 'int vkb_tex_stale('))

    def test_no_temporary_diagnostics(self):
        for name, text in self.text.items():
            with self.subTest(source=name):
                self.assertNotRegex(text, r'TOTK_REFRESH_R8|TOTK_FONT_UPLOAD_AUDIT')

    def test_controller_proof_and_v2_art_unchanged(self):
        proof = json.loads((ART / 'controller-hook-build.json').read_text())
        self.assertEqual(hashlib.sha256((SOURCE / 'src/gfx/vkb_tex.c').read_bytes()).hexdigest(),
                         proof['runtime_after_sha256'])
        self.assertEqual(proof['header_sha256'],
                         '3c843d31847ea01e9cddc58e407f9665ab64c030a30def184885601b2135088f')
        self.assertIn(proof['expected_elf_marker'], self.tex)
        self.assertIn('view = 2;', body(self.tex, 'static int deck_controller_upload('))
        self.assertEqual(hashlib.sha256((SOURCE / 'src/gfx/totk_deck_bitmaps.h').read_bytes()).hexdigest(),
                         proof['header_sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    SOURCE = args.source.resolve(strict=True)
    unittest.main(argv=[__file__, *remaining])
