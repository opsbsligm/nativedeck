// GPL-3.0-or-later. Included after the exact candidate with dependency-only shim.
static const vkb_bc7_key basekey={1,9}, newkey={2,9};
static void check(vkb_bc7_key k,int wantfmt,size_t n,uint8_t value){
    int fmt=-1;size_t len=0;uint8_t b[32];assert(n<=sizeof b);
    assert(vkb_bc7_lookup(k,&fmt,&len));assert(fmt==wantfmt&&len==n);
    memset(b,0,sizeof b);assert(!vkb_bc7_read(k,b,n+1));
    assert(vkb_bc7_read(k,b,n));for(size_t i=0;i<n;i++)assert(b[i]==value);
}
static void *concurrent(void *arg){
    uint64_t id=(uintptr_t)arg;
    for(uint64_t i=0;i<600;i++){
        vkb_bc7_key k={1000+id*600+i,77};uint8_t b[16];memset(b,(int)id,16);
        vkb_bc7_store(k,b,16);check(k,VKB_BC_7,16,(uint8_t)id);
        vkb_bc7_store(newkey,b,16);check(newkey,VKB_BC_7,16,0x22);
        check(basekey,VKB_BC_7,16,0x11);
    }return NULL;
}
int main(int argc,char **argv){
    assert(argc==2);uint8_t b[16];memset(b,0x22,16);
    if(!strcmp(argv[1],"fail")){
        int fmt;size_t n;assert(!vkb_bc7_lookup(basekey,&fmt,&n));
        vkb_bc7_store(newkey,b,16);assert(!vkb_bc7_has(newkey,16));assert(g_open==-1);return 0;
    }
    if(!strcmp(argv[1],"duplicate")){
        check(basekey,VKB_BC_1,8,0x44);vkb_bc7_store(basekey,b,16);
        check(basekey,VKB_BC_1,8,0x44);return 0;
    }
    check(basekey,VKB_BC_7,16,0x11);
    if(!strcmp(argv[1],"only-base"))return 0;
    if(!strcmp(argv[1],"io-pack")||!strcmp(argv[1],"io-idx")){
        signal(SIGXFSZ,SIG_IGN);
        struct rlimit lim={ !strcmp(argv[1],"io-pack")?8:32, RLIM_INFINITY };
        assert(!setrlimit(RLIMIT_FSIZE,&lim));
        vkb_bc7_store(newkey,b,16);assert(g_open==-1);
        assert(!vkb_bc7_has(newkey,16));
        vkb_bc7_store((vkb_bc7_key){4,9},b,16);assert(g_open==-1);return 0;
    }
    if(!strcmp(argv[1],"reload")){
        check(newkey,VKB_BC_7,16,0x22);
        if(g_overlay)assert(g_tab&&g_base&&g_pack);
        return 0;
    }
    if(!strcmp(argv[1],"concurrent-reload")){
        for(uint64_t t=0;t<8;t++)for(uint64_t i=0;i<600;i++)check((vkb_bc7_key){1000+t*600+i,77},0,16,(uint8_t)t);
        check(newkey,0,16,0x22);return 0;
    }
    vkb_bc7_store(basekey,b,16);check(basekey,0,16,0x11);
    vkb_bc7_store((vkb_bc7_key){0,0},b,16);
    vkb_bc_store((vkb_bc7_key){3,9},b,16,42);
    vkb_bc7_store((vkb_bc7_key){3,9},b,0);
    vkb_bc7_store((vkb_bc7_key){3,9},NULL,16);
    if(SIZE_MAX>UINT32_MAX)vkb_bc7_store((vkb_bc7_key){3,9},b,(size_t)UINT32_MAX+1);
    assert(!vkb_bc7_has((vkb_bc7_key){3,9},16));
    vkb_bc7_store(newkey,b,16);check(newkey,0,16,0x22);
    if(!strcmp(argv[1],"concurrent")){
        pthread_t t[8];for(uintptr_t i=0;i<8;i++)assert(!pthread_create(t+i,NULL,concurrent,(void *)i));
        for(int i=0;i<8;i++)assert(!pthread_join(t[i],NULL));
    }
    if(!strcmp(argv[1],"queue")){
        uint8_t rgba[64]={0};vkb_bc7_key k={909,66};vkb_bc7_queue(k,rgba,4,4,1,0);
        int found=0;for(int i=0;i<1000;i++){if(vkb_bc7_has(k,16)){found=1;break;}usleep(1000);}
        assert(found);check(k,0,16,0x5c);
    }
    puts("PASS native cache operations");return 0;
}
