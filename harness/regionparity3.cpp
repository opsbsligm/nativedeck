// SPDX-License-Identifier: GPL-3.0-or-later
// Paracy#3c: macro-region parity with a SOUND divergence classifier.
//
// Replaces regionparity2.cpp's "explained" heuristic, which compared live batch tags
// only against each other and therefore missed the case where a later batch restarts at
// the SAME address as an older snapshot and overwrites it uniformly (all tags inside the
// region then agree, yet the content/length changed).
//
// Sound rule: Eden's snapshot for key m was produced by exactly one upload batch b(m).
// ScarletNX hashes the live maximal same-tag run at m. Therefore:
//   if every address in Eden's snapshot region still carries tag b(m) in SNX's live RAM,
//   then no later upload touched that region, the live run cannot have grown or shrunk,
//   and the word sequence is the one Eden snapshotted  => hashes MUST be bit-identical.
//   Anything else is only possible if some address in the snapshot region was re-tagged by
//   a later batch  => divergence is explained by the snapshot-vs-live semantic class.
// unexplained != 0 is the only outcome that would indicate a real model/porting gap.
#include <cstdint>
#include <cstdio>
#include <algorithm>
#include <random>
#include <vector>

using u32 = uint32_t;
using u64 = uint64_t;

static u64 hash_word(u64 h, u32 w) {
    const u64 m = 0xC6A4A7935BD1E995ull;
    u64 k = w;
    k *= m; k ^= k >> 47; k *= m;
    h ^= k; h *= m;
    return h + 0xE6546B64ull;
}
static u64 hash_range(const std::vector<u32>& v) {
    u64 h = 0;
    for (u32 w : v) h = hash_word(h, w);
    return h;
}

// ---- Eden faithful model (SchwegelBin/eden MacroEngine), now carrying the snapshot batch id.
// Key == load_mme.instruction_ptr at upload time; ClearCode targets the NEW ptr value
// (registers are written before ProcessMethodCall); AddCode never auto-increments.
struct Eden3 {
    struct Entry { u32 key; u32 batch; std::vector<u32> words; };
    std::vector<Entry> uploaded;  // ankerl::unordered_dense => insertion order by default
    u32 ptr = 0, cur_batch = 0;
    bool shuffle_scan = false;  // when set, the range-match scan order is randomised per lookup

    void start_batch(u32 p, u32 bid) {
        ptr = p; cur_batch = bid;
        for (size_t i = 0; i < uploaded.size(); i++)
            if (uploaded[i].key == p) { uploaded.erase(uploaded.begin() + i); return; }
    }
    void add_code(u32 d) {
        for (auto& e : uploaded) if (e.key == ptr) { e.words.push_back(d); return; }
        uploaded.push_back({ptr, cur_batch, std::vector<u32>{d}});
    }
    // Eden's answer for a call at `method`; false == upstream ASSERT "was not uploaded".
    bool hash_for(u32 method, u64& out, u32& base, u32& len, u32& snap_batch, std::mt19937_64* sk = nullptr) {
        if (shuffle_scan && sk && uploaded.size() > 1)
            std::shuffle(uploaded.begin(), uploaded.end(), *sk);
        for (auto& e : uploaded)
            if (e.key == method) {
                out = hash_range(e.words); base = e.key; len = (u32)e.words.size();
                snap_batch = e.batch; return true;
            }
        for (auto& e : uploaded) {
            if (method >= e.key && (method - e.key) < (u32)e.words.size()) {
                std::vector<u32> rebased(e.words.begin() + (method - e.key), e.words.end());
                u64 h = hash_range(rebased);
                uploaded.push_back({method, e.batch, std::move(rebased)});
                out = h; base = method; len = (u32)uploaded.back().words.size();
                snap_batch = uploaded.back().batch; return true;
            }
        }
        return false;
    }
};

// ---- SNX faithful model (ScarletNX mme.c): live instruction RAM + monotonic batch tags.
struct Snx2 {
    static const u32 N = 0x2000;
    std::vector<u32> code = std::vector<u32>(N, 0);
    std::vector<u32> tag = std::vector<u32>(N, 0);
    std::vector<u32> start = std::vector<u32>(0x80, 0);
    u32 upload = 0, cur = 0, start_ptr = 0, batch = 0;

    u32 begin() { batch++; return batch; }  // mme_upload_ptr: batch++
    void write_ptr(u32 v, u32 bid) { upload = v; cur = bid; }
    void add_code(u32 d) { u32 at = upload++ & 0x1FFF; code[at] = d; tag[at] = cur; }
    void bind(u32 v) { start[start_ptr++ & 0x7F] = v; }

    bool hash_for(u32 addr, u64& out, u32& base, u32& len) const {
        u32 s = addr & 0x1FFF, b = tag[s], n = 0;
        if (!b) { out = 0; base = s; len = 0; return false; }
        while (n < N && tag[(s + n) & 0x1FFF] == b) n++;
        std::vector<u32> words;
        for (u32 i = 0; i < n; i++) words.push_back(code[(s + i) & 0x1FFF]);
        out = hash_range(words); base = s; len = n; return true;
    }
    // the sound classifier: was any word of Eden's snapshot region re-tagged after the snapshot?
    bool snapshot_region_retaken(u32 base, u32 len, u32 snap_batch) const {
        u32 s = base & 0x1FFF;
        for (u32 i = 0; i < len; i++)
            if (tag[(s + i) & 0x1FFF] != snap_batch) return true;
        return false;
    }
};

struct Stats {
    long long compared = 0, identical = 0, eden_assert = 0, rebased = 0;
    long long explained = 0, unexplained = 0, order_sensitive = 0;
};

static void report(const char* name, const Stats& st) {
    printf("[%s]\n  hashes compared = %lld   bit-identical = %lld   eden ASSERT(no region) = %lld\n",
           name, st.compared, st.identical, st.eden_assert);
    printf("  divergences explained by snapshot re-tagging = %lld\n", st.explained);
    printf("  divergences UNEXPLAINED                      = %lld\n", st.unexplained);
}

struct Case { u32 m; int order; };

int main() {
    Stats real, disjoint, adversarial;

    // ---- Regime R: the REAL captured deko3d pattern (14 overlapping suffixes of ONE
    // 181-word batch at word 0, bind order as first seen on hardware). Also proves the
    // answer is independent of the map's iteration order, which is the only thing that
    // could make ankerl::unordered_dense's bucket order observable. ----
    {
        const u32 starts[14] = {0, 23, 55, 67, 74, 106, 112, 116, 123, 129, 139, 149, 169, 176};
        const int order[14]  = {5, 2, 12, 3, 13, 9, 10, 11, 6, 4, 0, 8, 7, 1};
        std::mt19937_64 rng(0xDEC0DE37ull), sk(0x1234ull);

        auto run_once = [&](bool shuffle, const std::vector<u32>& words,
                            std::vector<std::array<u64,3>>& out) {
            Eden3 e; Snx2 s;
            e.shuffle_scan = shuffle;
            u32 bid = s.begin(); e.start_batch(0, bid); s.write_ptr(0, bid);
            for (u32 w : words) { e.add_code(w); s.add_code(w); }
            s.bind(0);
            out.clear();
            for (int oi = 0; oi < 14; oi++) {
                u32 m = starts[order[oi]];
                u64 he = 0, hs = 0; u32 be = 0, le = 0, bs = 0, ls = 0, sb = 0;
                bool oe = e.hash_for(m, he, be, le, sb, &sk), os = s.hash_for(m, hs, bs, ls);
                if (!oe || !os) { real.eden_assert++; out.push_back({~0ull, ~0ull, ~0ull}); continue; }
                real.compared++;
                if (he == hs && be == bs && le == ls) real.identical++;
                else if (s.snapshot_region_retaken(be, le, sb)) real.explained++;
                else {
                    real.unexplained++;
                    if (real.unexplained < 4)
                        printf("  R MISMATCH m=%u eden=[%u,%u) snx=[%u,%u) snap_batch=%u tag=%u\n",
                               m, be, be + le, bs, bs + ls, sb, s.tag[be & 0x1FFF]);
                }
                out.push_back({he, be, le});
            }
        };

        for (int iter = 0; iter < 50000; iter++) {
            std::vector<std::array<u64,3>> a, b;
            std::vector<u32> words(181);
            for (auto& w : words) w = (u32)rng();   // ONE batch, both runs share it
            run_once(false, words, a);
            run_once(true, words, b);   // identical content, randomised map iteration order
            if (a != b) {
                real.order_sensitive++;
                if (real.order_sensitive < 4) {
                    for (int k = 0; k < 14; k++)
                        if (a[k] != b[k])
                            printf("  R order-sensitive iter=%d idx=%d ordered=[%llu,%u+%u) shuffled=[%llu,%u+%u)\n",
                                   iter, k, (unsigned long long)a[k][0], (u32)a[k][1], (u32)a[k][2],
                                   (unsigned long long)b[k][0], (u32)b[k][1], (u32)b[k][2]);
                }
            }
        }
    }

    // ---- Regime N: NVN-shaped incremental uploads, pairwise DISJOINT ranges. ----
    {
        std::mt19937_64 rng(0x5EEDB0B5ull);
        for (int iter = 0; iter < 200000; iter++) {
            Eden3 e; Snx2 s;
            std::vector<u32> binds;
            u32 watermark = 0;
            int nb = 1 + (int)(rng() % 6);
            for (int g = 0; g < nb; g++) {
                u32 len = 1 + (u32)(rng() % 12);
                u32 p = watermark;
                watermark += len;
                u32 bid = s.begin(); e.start_batch(p, bid); s.write_ptr(p, bid);
                for (u32 i = 0; i < len; i++) { u32 w = (u32)rng(); e.add_code(w); s.add_code(w); }
                binds.push_back(p);
                if (rng() & 1) binds.push_back(p + 1 + (u32)(rng() % (len - 1 ? len - 1 : 1)));
                if ((rng() % 5) == 0) binds.push_back(0xFFFF);
            }
            for (u32 m : binds) {
                u64 he = 0, hs = 0; u32 be = 0, le = 0, bs = 0, ls = 0, sb = 0;
                bool oe = e.hash_for(m, he, be, le, sb), os = s.hash_for(m, hs, bs, ls);
                if (!oe) { disjoint.eden_assert++; continue; }
                if (!os) { disjoint.eden_assert++; continue; }
                disjoint.compared++;
                if (he == hs && be == bs && le == ls) { disjoint.identical++; continue; }
                if (s.snapshot_region_retaken(be, le, sb)) { disjoint.explained++; continue; }
                disjoint.unexplained++;
                if (disjoint.unexplained < 4)
                    printf("  N MISMATCH m=%u eden=[%u,%u) snx=[%u,%u)\n", m, be, be + le, bs, bs + ls);
            }
        }
    }

    // ---- Regime B: adversarial overlapping uploads, including same-address restarts. ----
    {
        std::mt19937_64 rng(0xBADC0DEull);
        for (int iter = 0; iter < 200000; iter++) {
            Eden3 e; Snx2 s;
            std::vector<u32> binds;
            int nb = 1 + (int)(rng() % 6);
            for (int g = 0; g < nb; g++) {
                u32 len = 1 + (u32)(rng() % 12);
                u32 p = (u32)(rng() % 24);
                u32 bid = s.begin(); e.start_batch(p, bid); s.write_ptr(p, bid);
                for (u32 i = 0; i < len; i++) { u32 w = (u32)rng(); e.add_code(w); s.add_code(w); }
                binds.push_back(p);
                if (rng() & 1) binds.push_back(p + 1 + (u32)(rng() % (len + 2)));
                if ((rng() % 5) == 0) binds.push_back((u32)(rng() % 40));
            }
            for (u32 m : binds) {
                u64 he = 0, hs = 0; u32 be = 0, le = 0, bs = 0, ls = 0, sb = 0;
                bool oe = e.hash_for(m, he, be, le, sb), os = s.hash_for(m, hs, bs, ls);
                if (!oe) { adversarial.eden_assert++; continue; }
                if (!os) { adversarial.eden_assert++; continue; }
                adversarial.compared++;
                if (he == hs && be == bs && le == ls) { adversarial.identical++; continue; }
                if (s.snapshot_region_retaken(be, le, sb)) { adversarial.explained++; continue; }
                adversarial.unexplained++;
                if (adversarial.unexplained < 6)
                    printf("  B MISMATCH m=%u eden=[%u,%u) snx=[%u,%u) snap_batch=%u tag=%u\n",
                           m, be, be + le, bs, bs + ls, sb, s.tag[be & 0x1FFF]);
            }
        }
    }

    report("R - real captured single-batch 14-suffix pattern", real);
    report("N - NVN-shaped disjoint incremental uploads", disjoint);
    report("B - adversarial overlapping + same-address restarts", adversarial);
    bool ok = (real.unexplained == 0) && (disjoint.unexplained == 0) && (adversarial.unexplained == 0);
    printf("%s\n", ok ? "PASS: zero unexplained divergences under the sound re-tagging rule" : "FAIL");
    return ok ? 0 : 1;
}
