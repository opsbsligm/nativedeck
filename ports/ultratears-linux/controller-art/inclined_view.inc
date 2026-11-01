/* Authored inclined view: retained BOTW front geometry under a documented
 * projection, plus a new, physically distinct shoulder/top rim. No game pixels.
 * Numeric grey and alpha handling follow the original RG8 art. */
#define SD_IPX(x,y) (290.0+((x)-288.0)*(0.94+0.04*(y)/288.0))
#define SD_IPY(y) (72.0+0.75*(y))
void sd_project_front_to_inclined(double sx,double sy,double *x,double *y) {
    if (x) *x=SD_IPX(sx,sy);
    if (y) *y=SD_IPY(sy);
}
/* Sample source RG8 at pixel-center coordinates. Interpolate premultiplied
 * grey/coverage, then convert back: transparent texels do not produce dark halos. */
static void inclined_sample(const uint8_t *src,double sx,double sy,double *g,double *a) {
    double px=sx-0.5,py=sy-0.5;
    int ix=(int)floor(px),iy=(int)floor(py);
    double fx=px-ix,fy=py-iy,alpha=0,premul=0;
    for (int j=0;j<2;j++) for (int i=0;i<2;i++) {
        int x=ix+i,y=iy+j;
        if (x<0 || x>=576 || y<0 || y>=288) continue;
        const uint8_t *s=src+((size_t)y*576+(size_t)x)*2;
        double weight=(i?fx:1-fx)*(j?fy:1-fy),coverage=s[1]/255.0;
        alpha+=coverage*weight; premul+=s[0]*coverage*weight;
    }
    *a=alpha; *g=alpha>0?premul/alpha:0;
}
static int draw_inclined_rg8(sd_renderer *ctx,uint8_t *lin) {
    const uint32_t w=580,h=340,row=1160;
    uint8_t *face=malloc((size_t)576*288*2);
    if (!face) return -1;
    draw_front_rg8(ctx,face);
    memset(lin,0,(size_t)row*h);
    #define DP(shape,grey) deck_paint(lin,row,w,h,(shape),(grey))
    #define DW(x,y,s,cap,mw) deck_word(ctx,lin,row,w,h,x,y,s,cap,mw)
    /* Visible case thickness behind the projected front upper edge. */
    DP(box(290,90,269,24,21),34);
    DP(ring(box(290,90,269,24,21),1),120);
    DP(seg(57,98,523,98,0.8f),67);
    /* Triggers sit behind/above the bumpers: four independently labelled keys.
     * These are shoulder geometry, not a pasted standalone top image. */
    for (int side=0;side<2;side++) {
        int x=side?522:58;
        DP(box(x,53,31,22,13),20);
        DP(ring(box(x,53,31,22,13),1),135);
        DP(box(x,79,33,11,5),49);
        DP(ring(box(x,79,33,11,5),0.8f),120);
        DW(x,49,side?"R2/RT":"L2/LT",9,49);
        DW(x,79,side?"R1/RB":"L1/LB",9,49);
    }
    /* Top-edge landmarks retain the visual vocabulary of the original top art. */
    DP(box(135,86,24,5,2),12);
    DW(124,86,"-",6,10); DW(146,86,"+",6,10);
    for (int x=225;x<310;x+=6) DP(seg(x,77,x,94,0.9f),9);
    DP(box(373,85,9,4,2),5);
    DP(circle(426,84,5),9); DP(circle(467,84,5),128);
    #undef DP
    #undef DW
    /* Inverse-map to pixel centers. Face is composited over the new upper rim.
     * Perspective widens slightly towards the lower face; y is foreshortened. */
    for (uint32_t y=0;y<h;y++) {
        double sy=((double)y+0.5-72.0)/0.75;
        if (sy<0 || sy>=288) continue;
        double scale=0.94+0.04*sy/288.0;
        for (uint32_t x=0;x<w;x++) {
            double sx=((double)x+0.5-290.0)/scale+288.0,g,a;
            if (sx<0 || sx>=576) continue;
            inclined_sample(face,sx,sy,&g,&a);
            if (a<=0) continue;
            uint8_t *p=lin+(size_t)y*row+x*2;
            double old=p[1]/255.0,combined=a+old*(1-a);
            p[0]=(uint8_t)lround((g*a+p[0]*old*(1-a))/combined);
            p[1]=(uint8_t)lround(combined*255);
        }
    }
    free(face); return 0;
}
