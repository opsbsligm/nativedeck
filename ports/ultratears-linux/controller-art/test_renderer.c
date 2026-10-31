/* Deliberately include the implementation to compare its RGBA output against
 * the unedited BOTW RG8 artwork, not a second hand-copied drawing. */
#include "steamdeck_renderer.c"
#include <assert.h>
static sd_renderer *reference_ctx;
static void reference_text(Canvas *c,const char *s,float x,float y,float cap,float max_w) {
    text(reference_ctx,c,s,x,y,cap,max_w);
}
static int resolve_kind(void) { return 1; }
static bool font_ready(void) { return reference_ctx!=NULL; }
#define ICONS_XBOX 1
#define LOG(...) ((void)0)
#define text reference_text
#define deck_paint reference_paint
#define deck_word reference_word
#define deck_draw reference_draw
#define deck_xbox_diagram reference_match
#include "vendor/botw_xbox_diagram.original.inc"
#undef text
#undef deck_paint
#undef deck_word
#undef deck_draw
#undef deck_xbox_diagram

static void compare_reference(sd_renderer *ctx,int front) {
    size_t w=front?580:576,h=front?340:100,sh=front?288:100;
    size_t stride=w*4+17,n=(h-1)*stride+w*4;
    uint8_t *p=malloc(n+32),*q=malloc(n+32),*ref=malloc(576*sh*2);
    assert(p && q && ref);
    memset(p,0xa5,n+32); memset(q,0xa5,n+32);
    reference_ctx=ctx; reference_draw(ref,1152,576,(uint32_t)sh);
    assert((front?sd_render_front(ctx,p,n,stride):sd_render_top(ctx,p,n,stride))==0);
    assert((front?sd_render_front(ctx,q,n,stride):sd_render_top(ctx,q,n,stride))==0);
    assert(!memcmp(p,q,n+32));
    size_t partial=0,opaque=0,intentional_changes=0;
    for (size_t y=0;y<h;y++) for (size_t x=0;x<w;x++) {
        const uint8_t *got=p+y*stride+x*4; unsigned grey=0,alpha=0;
        if ((!front || (x>=2 && x<578 && y>=26 && y<314))) {
            size_t sx=front?x-2:x,sy=front?y-26:y;
            const uint8_t *s=ref+(sy*576+sx)*2; alpha=s[1]; grey=alpha?s[0]:0;
        }
        /* The only intentional front change is the old+new D-pad footprint,
         * translated from source [18,45,58,99) to output [20,71,60,125).
         * Everything outside it still compares byte-for-byte to original art. */
        int same=got[0]==grey && got[1]==grey && got[2]==grey && got[3]==alpha;
        int allowed=front && x>=20 && x<60 && y>=71 && y<125;
        if (!allowed) assert(same); else intentional_changes+=!same;
        partial+=alpha>0 && alpha<255; opaque+=alpha==255;
    }
    assert(partial && opaque);
    assert(front?intentional_changes>0:intentional_changes==0);
    for (size_t y=0;y+1<h;y++) for (size_t x=w*4;x<stride;x++) assert(p[y*stride+x]==0xa5);
    for (size_t i=n;i<n+32;i++) assert(p[i]==0xa5);
    /* Bad arguments, overflow and short last rows must never write. */
    memset(p,0xa5,n+32);
    assert(render(ctx,p,n-1,stride,front)==-1);
    assert(render(ctx,p,n,w*4-1,front)==-1);
    assert(render(ctx,p,SIZE_MAX,SIZE_MAX,front)==-1);
    assert(render(NULL,p,n,stride,front)==-1);
    assert(render(ctx,NULL,n,stride,front)==-1);
    for (size_t i=0;i<n+32;i++) assert(p[i]==0xa5);
    printf("%s: original comparison outside explicit D-pad change region (%zu changed pixels), alpha, padding, bounds and determinism PASS\n",front?"front":"top",intentional_changes);
    free(p); free(q); free(ref);
}
static void letters(sd_renderer *ctx,int inclined) {
    size_t n=(size_t)580*340*4;
    uint8_t *p=malloc(n); assert(p && (inclined?sd_render_inclined(ctx,p,n,580*4):sd_render_front(ctx,p,n,580*4))==0);
    size_t count; const sd_anchor *a=inclined?sd_inclined_anchors(&count):sd_front_anchors(&count);
    for (size_t i=0;i<count;i++) if (!strncmp(a[i].id,"face_",5) || !strcmp(a[i].id,"left_stick") || !strcmp(a[i].id,"right_stick") || (inclined && a[i].source_x<0)) {
        unsigned bright=0;
        int cx=(int)lround(a[i].x),cy=(int)lround(a[i].y);
        for (int y=cy-7;y<=cy+7;y++) for (int x=cx-7;x<=cx+7;x++) {
            const uint8_t *v=p+((size_t)y*580+(size_t)x)*4;
            bright+=v[0]>180 && v[3]>200;
        }
        assert(bright>=3); printf("%s real font label %s at (%.9g,%.9g): %u bright pixels PASS\n",inclined?"inclined":"front",a[i].label,a[i].x,a[i].y,bright);
    }
    free(p);
}
static void inclined_checks(sd_renderer *ctx) {
    const size_t stride=580*4+23,n=339*stride+580*4;
    uint8_t *p=malloc(n+32),*q=malloc(n+32); assert(p && q);
    memset(p,0xa5,n+32); memset(q,0xa5,n+32);
    assert(sd_render_inclined(ctx,p,n,stride)==0 && sd_render_inclined(ctx,q,n,stride)==0);
    assert(!memcmp(p,q,n+32));
    for (size_t y=0;y<339;y++) for (size_t x=580*4;x<stride;x++) assert(p[y*stride+x]==0xa5);
    for (size_t i=n;i<n+32;i++) assert(p[i]==0xa5);
    /* Screen center proves this view retains the front face, not just a top rim. */
    const uint8_t *screen=p+190*stride+290*4;
    assert(screen[0]==19 && screen[3]==255);
    /* Verify inverse warp against original front texels over its unobstructed
     * central screen. New top edge lives above this region. */
    uint8_t *ref=malloc((size_t)576*288*2); assert(ref);
    reference_ctx=ctx; reference_draw(ref,1152,576,288);
    for (int y=150;y<230;y++) for (int x=160;x<420;x++) {
        double sy=(y+0.5-72)/0.75,sx=(x+0.5-290)/(0.94+0.04*sy/288)+288,g,a;
        inclined_sample(ref,sx,sy,&g,&a);
        const uint8_t *got=p+(size_t)y*stride+(size_t)x*4;
        assert(got[0]==(uint8_t)lround(g) && got[3]==(uint8_t)lround(a*255));
    }
    size_t count; const sd_anchor *anchors=sd_inclined_anchors(&count);
    assert(count==17);
    for (size_t i=0;i<count;i++) if (anchors[i].source_x>=0) {
        double x,y; sd_project_front_to_inclined(anchors[i].source_x,anchors[i].source_y,&x,&y);
        assert(fabs(x-anchors[i].x)<1e-12 && fabs(y-anchors[i].y)<1e-12);
    }
    memset(p,0xa5,n+32);
    assert(sd_render_inclined(ctx,p,n-1,stride)==-1);
    assert(sd_render_inclined(ctx,p,n,2319)==-1);
    assert(sd_render_inclined(ctx,p,SIZE_MAX,SIZE_MAX)==-1);
    assert(sd_render_inclined(NULL,p,n,stride)==-1);
    assert(sd_render_inclined(ctx,NULL,n,stride)==-1);
    for (size_t i=0;i<n+32;i++) assert(p[i]==0xa5);
    free(ref); free(p); free(q);
    puts("inclined: projected face retained, subpixel anchors, bounds, padding and determinism PASS");
}
int main(int argc,char **argv) {
    assert(argc==2);
    char error[160];
    assert(!sd_renderer_create(NULL,error,sizeof error) && error[0]);
    assert(!sd_renderer_create("/nonexistent/steamdeck-font.ttf",error,sizeof error) && error[0]);
    sd_renderer *ctx=sd_renderer_create(argv[1],error,sizeof error);
    if (!ctx) { fprintf(stderr,"%s\n",error); return 1; }
    reference_ctx=ctx;
    uint8_t dummy[2]={0}; assert(!reference_match(0,1,1,dummy,2));
    compare_reference(ctx,1); compare_reference(ctx,0); inclined_checks(ctx); letters(ctx,0); letters(ctx,1);
    sd_renderer *other=sd_renderer_create(argv[1],error,sizeof error); assert(other);
    sd_renderer_destroy(ctx); compare_reference(other,1); sd_renderer_destroy(other);
    sd_renderer_destroy(NULL); puts("ALL CHECKS PASS"); return 0;
}
