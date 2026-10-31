// Authored Steam Deck art, paired with botw_deck_layout.py callout transforms.
// No game texture is distributed. Only two exact SDK7 RG8 textures are replaced.
static void deck_paint(uint8_t *lin, uint32_t row, uint32_t w, uint32_t h, Shape shape, int grey) {
    for (uint32_t y=0;y<h;y++) for (uint32_t x=0;x<w;x++) {
        float a=cover(sd(&shape,x+.5f,y+.5f));
        if (!a) continue;
        uint8_t *p=lin+(uint64_t)y*row+x*2;
        float old=p[1]/255.0f, combined=a+old*(1-a);
        p[0]=(uint8_t)lroundf((grey*a+p[0]*old*(1-a))/combined);
        p[1]=(uint8_t)lroundf(combined*255);
    }
}
static void deck_word(uint8_t *lin,uint32_t row,uint32_t w,uint32_t h,
                      int cx,int cy,const char *label,float cap,float max_w) {
    Canvas c; text(&c,label,CELL/2.0f,CELL/2.0f,cap,max_w);
    for (int y=0;y<CELL;y++) for (int x=0;x<CELL;x++) {
        int X=cx+x-CELL/2,Y=cy+y-CELL/2;
        if(X<0||Y<0||X>=(int)w||Y>=(int)h) continue;
        float a=c.a[y*CELL+x]; uint8_t *p=lin+(uint64_t)Y*row+X*2;
        p[0]=(uint8_t)lroundf(p[0]*(1-a)+215*a);
    }
}
static void deck_draw(uint8_t *lin,uint32_t row,uint32_t w,uint32_t h) {
    for(uint32_t y=0;y<h;y++) memset(lin+(uint64_t)y*row,0,w*2);
    #define DP(shape,grey) deck_paint(lin,row,w,h,(shape),(grey))
    #define DW(x,y,s,cap,mw) deck_word(lin,row,w,h,x,y,s,cap,mw)
    if(h==288) {
        DP(box(288,144,275,103,32),32);
        DP(box(52,155,40,111,31),38); DP(box(524,155,40,111,31),38);
        DP(ring(box(288,144,275,103,32),1.1f),116);
        DP(box(288,143,151,101,9),10); DP(ring(box(288,143,151,101,9),1),92);
        DP(box(288,143,140,88,2),19);
        DW(267,144,"STEAM",10,42); DW(312,144,"DECK",10,36);
        for(int side=0;side<2;side++) {
            int x=side?470:88;
            DP(circle(x,88,17),8); DP(ring(circle(x,88,17),1.5f),142);
            DP(circle(x,88,12),52); DP(ring(circle(x,88,11),.7f),89);
            DW(x,89,side?"RS":"LS",8,19);
            int pad=side?506:70;
            DP(box(pad,173,28,28,5),13); DP(ring(box(pad,173,28,28,5),1),100);
            for(int y=222;y<=236;y+=4) DP(seg(pad-15,y,pad+15,y,.8f),100);
        }
        DP(box(38,65,6,19,2),100); DP(box(38,65,19,6,2),100);
        DP(box(38,65,4,17,1),9); DP(box(38,65,17,4,1),9);
        const int px[4]={517,535,499,517},py[4]={106,89,89,71};
        const char *letters[4]={"A","B","X","Y"};
        for(int i=0;i<4;i++) {
            DP(circle(px[i],py[i],10),10); DP(ring(circle(px[i],py[i],10),.7f),135);
            DW(px[i],py[i],letters[i],10,12);
        }
        DP(box(126,54,10,7,3),13); DP(box(450,54,10,7,3),13);
        DP(ring(box(124,53,3,2.5f,0),.6f),195); DP(ring(box(128,56,3,2.5f,0),.6f),195);
        for(int y=51;y<=57;y+=3) DP(seg(445,y,455,y,.6f),195);
        DP(box(119,231,17,7,5),12); DW(119,231,"STEAM",5,28);
        DP(box(457,231,14,7,5),12); DW(457,230,"...",8,20);
    } else {
        DP(box(288,52,276,25,19),34); DP(ring(box(288,52,276,25,19),1),120);
        DP(box(46,25,31,17,10),20); DP(ring(box(46,25,31,17,10),1),120);
        DP(box(529,25,31,17,10),20); DP(ring(box(529,25,31,17,10),1),120);
        DP(box(46,49,34,10,4),49); DP(box(530,49,34,10,4),49);
        DW(46,24,"L2/LT",8,42); DW(529,24,"R2/RT",8,42);
        DW(46,49,"L1/LB",8,42); DW(530,49,"R1/RB",8,42);
        DP(box(135,48,24,5,2),12); DW(124,49,"-",6,10); DW(146,49,"+",6,10);
        for(int x=225;x<310;x+=6) DP(seg(x,44,x,61,.9f),9);
        DP(box(373,50,9,4,2),5); DW(373,73,"USB-C",5,26);
        DP(circle(426,49,5),9); DP(circle(467,49,5),128);
    }
    #undef DP
    #undef DW
}
static bool deck_xbox_diagram(uint32_t format,uint32_t w,uint32_t h,uint8_t *lin,uint32_t row) {
    if(format!=0x0d||w!=576||(h!=288&&h!=100)||row<w*2) return false;
    uint64_t hash=0xcbf29ce484222325ull;
    for(uint32_t y=0;y<h;y++) for(uint32_t x=0;x<w*2;x++) hash=(hash^lin[(uint64_t)y*row+x])*0x100000001b3ull;
    if(hash!=(h==288?0x8b42a6ff21f5dea4ull:0x6e2b71b7ed623592ull)) return false;
    if(resolve_kind()!=ICONS_XBOX||!font_ready()) return true;
    deck_draw(lin,row,w,h);
    LOG("[glyphs] SDK7 Steam Deck diagram %ux%u: matched ABXY, sticks, touchpads, L1/L2 aliases\n",w,h);
    return true;
}
