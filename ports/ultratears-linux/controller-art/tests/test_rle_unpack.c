/* Decode the generated public header and compare every byte with native art. */
#include "totk_deck_bitmaps.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    assert(argc>=2 && argc%2==0);
    uint8_t *actual=malloc(ND_DECK_BYTES+32),*expected=malloc(ND_DECK_BYTES);
    assert(actual && expected && sizeof(nd_deck_run)==4);
    for (int view=1;view<=2;view++) {
        char path[4096]; int n=snprintf(path,sizeof path,"%s/%s.rgba",argv[1],view==1?"front":"inclined");
        assert(n>0 && (size_t)n<sizeof path);
        FILE *f=fopen(path,"rb"); assert(f);
        assert(fread(expected,1,ND_DECK_BYTES,f)==ND_DECK_BYTES && fgetc(f)==EOF); fclose(f);
        memset(actual,0xa5,ND_DECK_BYTES+32);
        assert(nd_deck_unpack(view,actual,ND_DECK_BYTES)==0);
        assert(!memcmp(actual,expected,ND_DECK_BYTES));
        for (size_t i=ND_DECK_BYTES;i<ND_DECK_BYTES+32;i++) assert(actual[i]==0xa5);
    }
    memset(actual,0xa5,ND_DECK_BYTES+32);
    assert(nd_deck_unpack(0,actual,ND_DECK_BYTES)==-1);
    assert(nd_deck_unpack(3,actual,ND_DECK_BYTES)==-1);
    assert(nd_deck_unpack(1,NULL,ND_DECK_BYTES)==-1);
    assert(nd_deck_unpack(2,actual,ND_DECK_BYTES-1)==-1);
    for (size_t i=0;i<ND_DECK_BYTES+32;i++) assert(actual[i]==0xa5);
    assert(nd_deck_source_view("0000000000000000000000000000000000000000000000000000000000000000")==0);
    for (int i=2;i<argc;i+=2) assert(nd_deck_source_view(argv[i])==atoi(argv[i+1]));
    free(actual); free(expected);
    puts("RLE C ABI, two-view exact roundtrip, whitelist, invalid-input and guard checks PASS");
    return 0;
}
