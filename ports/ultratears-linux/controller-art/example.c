#include "steamdeck_renderer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void anchors(void) {
    puts("{\"schema\":2,\"coordinate_system\":\"pixels, top-left origin, x right, y down\",\"game_layout_validated\":false,");
    puts("\"pixel_format\":\"RGBA8 straight alpha\",\"front_source\":[576,288],\"front_offset\":[2,26],");
    puts("\"inclined_projection\":{\"input\":\"original 576x288 front\",\"x\":\"290+(x-288)*(0.94+0.04*y/288)\",\"y\":\"72+0.75*y\",\"sampling\":\"inverse map pixel centers, alpha-weighted bilinear\"},");
    puts("\"resource_mapping\":{\"Controller_Console^w\":\"front\",\"Controller_Grip^w\":\"front\",\"Controller_Pro^w\":\"front\",\"Controller_Console1^w\":\"inclined\",\"Controller_Grip1^w\":\"inclined\",\"Controller_Pro1^w\":\"inclined\"},");
    for (int view=0;view<3;view++) {
        size_t count; const sd_anchor *a=view==0?sd_front_anchors(&count):view==1?sd_inclined_anchors(&count):sd_top_anchors(&count);
        const char *name=view==0?"front":view==1?"inclined":"top";
        printf("\"%s\":{\"width\":%d,\"height\":%d,\"anchors\":[\n",name,view==2?SD_TOP_WIDTH:SD_FRONT_WIDTH,view==2?SD_TOP_HEIGHT:SD_FRONT_HEIGHT);
        for (size_t i=0;i<count;i++) {
            printf("{\"id\":\"%s\",\"label\":\"%s\",\"source\":",a[i].id,a[i].label);
            if (a[i].source_x<0) printf("null"); else printf("[%d,%d]",a[i].source_x,a[i].source_y);
            printf(",\"pixel\":[%.17g,%.17g]}%s\n",a[i].x,a[i].y,i+1<count?",":"");
        }
        printf("]}%s\n",view<2?",":"");
    }
    puts("}");
}
int main(int argc,char **argv) {
    if (argc==2 && !strcmp(argv[1],"--anchors")) { anchors(); return 0; }
    if (argc!=4 || (strcmp(argv[1],"front") && strcmp(argv[1],"inclined") && strcmp(argv[1],"top"))) {
        fprintf(stderr,"Usage: %s front|inclined|top FONT.ttf OUTPUT.rgba\n       %s --anchors\n",argv[0],argv[0]); return 2;
    }
    char error[160]; sd_renderer *ctx=sd_renderer_create(argv[2],error,sizeof error);
    if (!ctx) { fprintf(stderr,"%s\n",error); return 1; }
    int front=!strcmp(argv[1],"front"),inclined=!strcmp(argv[1],"inclined"),full=front||inclined;
    size_t w=full?SD_FRONT_WIDTH:SD_TOP_WIDTH,h=full?SD_FRONT_HEIGHT:SD_TOP_HEIGHT,n=w*h*4;
    uint8_t *p=malloc(n);
    int rc=p?(front?sd_render_front(ctx,p,n,w*4):inclined?sd_render_inclined(ctx,p,n,w*4):sd_render_top(ctx,p,n,w*4)):-1;
    if (rc) { fprintf(stderr,"Render failed\n"); free(p); sd_renderer_destroy(ctx); return 1; }
    FILE *f=fopen(argv[3],"wb");
    if (!f) rc=-1;
    else { if (fwrite(p,1,n,f)!=n) rc=-1; if (fclose(f)) rc=-1; }
    free(p); sd_renderer_destroy(ctx);
    if (rc) { fprintf(stderr,"Output write failed\n"); return 1; }
    return 0;
}
