/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail_next;
static void *test_alloc(size_t n) { if (fail_next) { fail_next=0; return NULL; } return malloc(n); }
#define malloc test_alloc
#include "cpu_texture_shadow.h"
#undef malloc

static nd_cpu_shadow concurrent;
static unsigned char stable[4096];
static void *compare_worker(void *unused) {
    (void)unused;
    for (int n=0;n<400;n++) {
        assert(nd_shadow_capture(&concurrent,stable,sizeof stable));
        assert(!nd_shadow_changed(&concurrent,stable,sizeof stable));
    }
    return NULL;
}
int main(void) {
    unsigned char *input=calloc(1,ND_SHADOW_MAX);
    assert(input);
    nd_cpu_shadow s={0};
    const size_t bytes=8u*1024u*1024u;
    assert(nd_shadow_changed(&s,input,bytes));
    const unsigned char *snapshot=nd_shadow_capture(&s,input,bytes);
    assert(snapshot && !memcmp(snapshot,input,bytes));
    for (int n=0;n<20;n++) assert(!nd_shadow_changed(&s,input,bytes));
    size_t positions[]={0,15664,bytes/2,bytes-1};
    for (unsigned n=0;n<sizeof positions/sizeof positions[0];n++) {
        input[positions[n]]=0x41;
        assert(nd_shadow_changed(&s,input,bytes));
        assert(snapshot[positions[n]]==0);
        assert(nd_shadow_capture(&s,input,bytes));
        assert(!nd_shadow_changed(&s,input,bytes));
        input[positions[n]]=0;
        assert(nd_shadow_changed(&s,input,bytes));
        assert(nd_shadow_capture(&s,input,bytes));
    }
    assert(!nd_shadow_capture(&s,NULL,bytes));
    assert(nd_shadow_changed(&s,input,0));
    assert(nd_shadow_changed(&s,input,ND_SHADOW_MAX+1u));
    nd_shadow_release(&s);assert(!s.data && !s.size && nd_shadow_bytes==0);
    fail_next=1;
    assert(!nd_shadow_capture(&s,input,bytes));
    assert(nd_shadow_changed(&s,input,bytes));
    assert(nd_shadow_bytes==0);
    nd_cpu_shadow full[4]={{0}},overflow={0};
    for (int n=0;n<4;n++) assert(nd_shadow_capture(&full[n],input,ND_SHADOW_MAX));
    assert(nd_shadow_bytes==ND_SHADOW_BUDGET);
    assert(!nd_shadow_capture(&overflow,input,1));
    assert(nd_shadow_changed(&overflow,input,1));
    nd_shadow_release(&full[0]);
    assert(nd_shadow_capture(&overflow,input,1));
    for (int n=0;n<4;n++)nd_shadow_release(&full[n]);
    nd_shadow_release(&overflow);assert(nd_shadow_bytes==0);
    assert(nd_shadow_capture(&s,input,bytes));
    assert(nd_shadow_capture(&s,input,4096));
    assert(nd_shadow_bytes==4096);nd_shadow_release(&s);
    pthread_t threads[4];
    for (int n=0;n<4;n++)assert(!pthread_create(&threads[n],NULL,compare_worker,NULL));
    for (int n=0;n<4;n++)assert(!pthread_join(threads[n],NULL));
    nd_shadow_release(&concurrent);assert(nd_shadow_bytes==0);
    free(input);
    puts("exact bytes, unchanged reuse, changed edges, OOM fallback, bounded budget, resize, concurrency, release: PASS");
    return 0;
}
