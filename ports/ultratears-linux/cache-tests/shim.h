// Test-only dependencies. GPL-3.0-or-later. Cache implementation is unmodified.
#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <pthread.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <assert.h>
#include <sys/resource.h>
#include <signal.h>
#define LOG(...) do { fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define die(s) do { fprintf(stderr,"fatal: %s\n",s); abort(); } while (0)
#define _mkdir(p) mkdir(p,0700)
#define _fseeki64 fseeko
#define _ftelli64 ftello
#define pthread_setname_np(n) pthread_setname_np(pthread_self(),n)
enum { VKB_BC_7 = 0, VKB_BC_1 = 1 };
typedef struct { uint64_t a,b; } vkb_bc7_key;
typedef vkb_bc7_key bc7_key;
void vkb_bc_store(vkb_bc7_key,const uint8_t *,size_t,int);
static bc7_key bc7_key_of(const uint8_t *p,size_t n,uint32_t w,uint32_t h,uint32_t d,uint32_t bw,uint32_t bh) {
    (void)p;(void)n;(void)w;(void)h;(void)d;(void)bw;(void)bh;return (bc7_key){1,2};
}
static void *linux_map_readonly(const char *path,size_t minimum,size_t *size) {
    if(getenv("HARNESS_NO_MMAP"))return NULL;
    int fd=open(path,O_RDONLY);if(fd<0)return NULL;
    struct stat st;if(fstat(fd,&st)||st.st_size<(off_t)minimum){close(fd);return NULL;}
    void *m=mmap(NULL,(size_t)st.st_size,PROT_READ,MAP_PRIVATE,fd,0);close(fd);
    if(m==MAP_FAILED)return NULL;*size=(size_t)st.st_size;return m;
}
static void linux_worker_priority(int n){(void)n;}
static uint64_t runtime_now_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static size_t bc7_size(uint32_t w,uint32_t h,uint32_t d){return ((w+3)/4)*((h+3)/4)*d*16;}
static void bc7_encode(const uint8_t *in,uint32_t w,uint32_t h,uint32_t d,int srgb,int q,uint8_t *out){(void)in;(void)srgb;(void)q;memset(out,0x5c,bc7_size(w,h,d));}
static void bc1_encode(const uint8_t *in,uint32_t w,uint32_t h,uint32_t d,int q,uint8_t *out){(void)in;(void)q;memset(out,0x33,bc7_size(w,h,d)/2);}
