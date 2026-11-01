/* Hand-maintained public API; included by the derived implementation. */
static void font_error(char *error, size_t size, const char *message) {
    if (error && size) snprintf(error,size,"%s",message);
}
sd_renderer *sd_renderer_create(const char *path,char *error,size_t error_size) {
    font_error(error,error_size,"");
    if (!path) { font_error(error,error_size,"Font path is NULL"); return NULL; }
    FILE *f=fopen(path,"rb");
    if (!f) { font_error(error,error_size,"Cannot open required font; no fallback"); return NULL; }
    if (fseek(f,0,SEEK_END)) { fclose(f); font_error(error,error_size,"Cannot seek font"); return NULL; }
    long n=ftell(f);
    if (n<12 || n>16*1024*1024 || fseek(f,0,SEEK_SET)) {
        fclose(f); font_error(error,error_size,"Invalid font length"); return NULL;
    }
    sd_renderer *ctx=calloc(1,sizeof *ctx);
    if (!ctx) { fclose(f); font_error(error,error_size,"Allocation failure"); return NULL; }
    ctx->font_data=malloc((size_t)n);
    if (!ctx->font_data) {
        fclose(f); sd_renderer_destroy(ctx); font_error(error,error_size,"Allocation failure"); return NULL;
    }
    size_t got=fread(ctx->font_data,1,(size_t)n,f); fclose(f);
    /* The bundled font is trusted, not an untrusted-font validation interface. */
    int offset=got==(size_t)n ? stbtt_GetFontOffsetForIndex(ctx->font_data,0) : -1;
    if (offset<0 || offset>n-12 || !stbtt_InitFont(&ctx->font,ctx->font_data,offset)) {
        sd_renderer_destroy(ctx); font_error(error,error_size,"Cannot initialize font"); return NULL;
    }
    const char *required="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+./";
    for (const char *p=required;*p;p++) if (!stbtt_FindGlyphIndex(&ctx->font,*p)) {
        sd_renderer_destroy(ctx); font_error(error,error_size,"Font lacks required real label glyphs"); return NULL;
    }
    return ctx;
}
void sd_renderer_destroy(sd_renderer *ctx) {
    if (ctx) { free(ctx->font_data); free(ctx); }
}
/* view=0 standalone top, 1 unchanged front, 2 inclined. */
static int render(sd_renderer *ctx,uint8_t *rgba,size_t bytes,size_t stride,int view) {
    if (view<0 || view>2) return -1;
    const int front=view==1,inclined=view==2;
    const size_t w=view?SD_FRONT_WIDTH:SD_TOP_WIDTH,h=view?SD_FRONT_HEIGHT:SD_TOP_HEIGHT;
    if (!ctx || !rgba || stride<w*4 || stride>(SIZE_MAX-w*4)/(h-1) || bytes<(h-1)*stride+w*4) return -1;
    const size_t src_h=inclined?SD_INCLINED_HEIGHT:front?SD_NATIVE_FRONT_HEIGHT:SD_TOP_HEIGHT;
    const size_t src_w=inclined?SD_INCLINED_WIDTH:SD_NATIVE_FRONT_WIDTH;
    uint8_t *rg=malloc(src_w*src_h*2);
    if (!rg) return -1;
    if (inclined) { if (draw_inclined_rg8(ctx,rg)) { free(rg); return -1; } }
    else if (front) draw_front_rg8(ctx,rg); else draw_top_rg8(ctx,rg);
    for (size_t y=0;y<h;y++) memset(rgba+y*stride,0,w*4);
    const size_t dx=front?SD_FRONT_OFFSET_X:0,dy=front?SD_FRONT_OFFSET_Y:0;
    for (size_t y=0;y<src_h;y++) for (size_t x=0;x<src_w;x++) {
        const uint8_t *s=rg+(y*src_w+x)*2;
        uint8_t *d=rgba+(y+dy)*stride+(x+dx)*4;
        d[0]=d[1]=d[2]=s[1]?s[0]:0; d[3]=s[1];
    }
    free(rg); return 0;
}
int sd_render_front(sd_renderer *ctx,uint8_t *rgba,size_t bytes,size_t stride) { return render(ctx,rgba,bytes,stride,1); }
int sd_render_inclined(sd_renderer *ctx,uint8_t *rgba,size_t bytes,size_t stride) { return render(ctx,rgba,bytes,stride,2); }
int sd_render_top(sd_renderer *ctx,uint8_t *rgba,size_t bytes,size_t stride) { return render(ctx,rgba,bytes,stride,0); }
#define F(id,label,x,y) {id,label,x,y,(x)+SD_FRONT_OFFSET_X,(y)+SD_FRONT_OFFSET_Y}
static const sd_anchor front_anchors[]={
    F("left_stick","LS",88,88), F("right_stick","RS",470,88),
    F("dpad_center","D-pad",38,79), F("view","View",126,54), F("menu","Menu",450,54),
    F("face_south","A",517,106), F("face_east","B",535,89),
    F("face_west","X",499,89), F("face_north","Y",517,71),
    F("left_touchpad","",70,173), F("right_touchpad","",506,173),
    F("steam","STEAM",119,231), F("quick_access","...",457,231)
};
#undef F
#define I(id,label,x,y) {id,label,x,y,SD_IPX(x,y),SD_IPY(y)}
static const sd_anchor inclined_anchors[]={
    I("left_stick","LS",88,88), I("right_stick","RS",470,88),
    I("dpad_center","D-pad",38,79), I("view","View",126,54), I("menu","Menu",450,54),
    I("face_south","A",517,106), I("face_east","B",535,89),
    I("face_west","X",499,89), I("face_north","Y",517,71),
    I("left_touchpad","",70,173), I("right_touchpad","",506,173),
    I("steam","STEAM",119,231), I("quick_access","...",457,231),
    {"left_trigger","L2/LT",-1,-1,58,53}, {"right_trigger","R2/RT",-1,-1,522,53},
    {"left_bumper","L1/LB",-1,-1,58,79}, {"right_bumper","R1/RB",-1,-1,522,79}
};
#undef I
#define T(id,label,x,y) {id,label,x,y,x,y}
static const sd_anchor top_anchors[]={
    T("left_trigger","L2/LT",46,25), T("right_trigger","R2/RT",529,25),
    T("left_bumper","L1/LB",46,49), T("right_bumper","R1/RB",530,49),
    T("volume_down","-",124,49), T("volume_up","+",146,49),
    T("usb_c","USB-C",373,50), T("headphone_jack","",426,49), T("power","",467,49)
};
#undef T
const sd_anchor *sd_front_anchors(size_t *count) {
    if (count) *count=sizeof front_anchors/sizeof *front_anchors;
    return front_anchors;
}
const sd_anchor *sd_top_anchors(size_t *count) {
    if (count) *count=sizeof top_anchors/sizeof *top_anchors;
    return top_anchors;
}
const sd_anchor *sd_inclined_anchors(size_t *count) {
    if (count) *count=sizeof inclined_anchors/sizeof *inclined_anchors;
    return inclined_anchors;
}
