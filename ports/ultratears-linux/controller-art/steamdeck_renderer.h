/* Independent authored Steam Deck art. See NOTICE.md for provenance/licensing. */
#ifndef STEAMDECK_RENDERER_H
#define STEAMDECK_RENDERER_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { SD_FRONT_WIDTH=580, SD_FRONT_HEIGHT=340,
       SD_INCLINED_WIDTH=580, SD_INCLINED_HEIGHT=340,
       SD_TOP_WIDTH=576, SD_TOP_HEIGHT=100,
       SD_NATIVE_FRONT_WIDTH=576, SD_NATIVE_FRONT_HEIGHT=288,
       SD_FRONT_OFFSET_X=2, SD_FRONT_OFFSET_Y=26 };
typedef struct sd_renderer sd_renderer;
typedef struct sd_anchor {
    const char *id;
    const char *label;
    int source_x, source_y;
    double x, y;
} sd_anchor;
/* Load a trusted TTF. NULL means failure, with a message if error_size > 0.
 * The bundled FiraSans-SemiBold.ttf is the reference font. No fallback font.
 * One context per concurrent caller; no process-global mutable renderer state. */
sd_renderer *sd_renderer_create(const char *font_path, char *error, size_t error_size);
void sd_renderer_destroy(sd_renderer *renderer);
/* Fixed-size, top-down RGBA8, straight alpha, grey values retained from BOTW art.
 * Transparent pixels have RGB=0. No colour-space conversion is performed.
 * stride >= width*4; bytes >= (height-1)*stride+width*4.
 * Returns 0 on success, -1 on bad arguments/allocation failure. Invalid arguments
 * leave the destination untouched. Row padding is never changed. No game I/O. */
int sd_render_front(sd_renderer *renderer, uint8_t *rgba, size_t bytes, size_t stride);
/* Compressed/projected front face plus separately drawn shoulder top edge.
 * This is a distinct 580x340 view, not the standalone top image. */
int sd_render_inclined(sd_renderer *renderer, uint8_t *rgba, size_t bytes, size_t stride);
int sd_render_top(sd_renderer *renderer, uint8_t *rgba, size_t bytes, size_t stride);
/* Pixel coordinates, origin at top left; not game layout/pane coordinates.
 * Array lifetime is static. source_* use the original BOTW authored canvas. */
const sd_anchor *sd_front_anchors(size_t *count);
/* Projected face anchors retain subpixel coordinates; new shoulder anchors have
 * source_x=source_y=-1 because they are not part of the original front canvas.
 * x/y denote geometric centers, not necessarily the rounded text baseline. */
const sd_anchor *sd_inclined_anchors(size_t *count);
const sd_anchor *sd_top_anchors(size_t *count);
/* Projection of original 576x288 front coordinates, NOT translated front pixels.
 * x'=290+(x-288)*(0.94+0.04*y/288), y'=72+0.75*y. */
void sd_project_front_to_inclined(double source_x, double source_y, double *x, double *y);
#ifdef __cplusplus
}
#endif
#endif
