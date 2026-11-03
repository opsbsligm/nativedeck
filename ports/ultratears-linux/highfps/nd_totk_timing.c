/* Linux static-recompile adaptation of MacNativeGames' v1.4.3 measured frame clock.
 * Keep the game's existing slow-motion selector; cloth has its separate clock.
 * No game instructions or assets are included in this runtime unit. */
#include <stdint.h>
#include <stdatomic.h>
#include <string.h>
#include <stdio.h>
static _Atomic uint32_t step_bits = 0x3c888889; /* 1/60 second */
float nd_totk_step(float hz) {
    uint32_t bits = atomic_load_explicit(&step_bits, memory_order_acquire);
    float f; memcpy(&f, &bits, sizeof f); return f * hz;
}
void runtime_frame_step_update(uint64_t now) {
    static uint64_t previous;
    static double samples[5];
    static unsigned count, next;
    if (!previous) { previous = now; return; }
    if (now <= previous) { previous = now; count = next = 0; return; }
    double dt = (now - previous) * 1e-9; previous = now;
    if (dt > 0.25 || dt < 0.001) { count = next = 0; return; }
    if (dt > 1.0 / 15.0) dt = 1.0 / 15.0;
    samples[next++ % 5] = dt; if (count < 5) count++;
    double total = 0; for (unsigned i = 0; i < count; i++) total += samples[i];
    float seconds = (float)(total / count); uint32_t bits;
    memcpy(&bits, &seconds, sizeof bits);
    atomic_store_explicit(&step_bits, bits, memory_order_release);
}
__attribute__((constructor)) static void timing_notice(void) {
    fprintf(stderr, "[nativedeck] TOTK 1.4.3 native 60fps controller + measured frame step + cloth clock enabled\n");
}
