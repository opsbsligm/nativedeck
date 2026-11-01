CC = cc
CFLAGS = -O2 -std=c11 -Wall -Wextra -Wpedantic -Werror
LDLIBS = -lm
BUILD = build
FONT = vendor/FiraSans-SemiBold.ttf
.PHONY: all anchors check reference check-rle clean
all: $(BUILD)/render_deck $(BUILD)/test_renderer
$(BUILD):
	mkdir -p $(BUILD)
$(BUILD)/render_deck: example.c steamdeck_renderer.c steamdeck_renderer.h renderer_api.inc inclined_view.inc vendor/imstb_truetype.h | $(BUILD)
	$(CC) $(CFLAGS) example.c steamdeck_renderer.c $(LDLIBS) -o $@
$(BUILD)/test_renderer: test_renderer.c steamdeck_renderer.c steamdeck_renderer.h renderer_api.inc inclined_view.inc vendor/imstb_truetype.h vendor/botw_xbox_diagram.original.inc | $(BUILD)
	$(CC) $(CFLAGS) test_renderer.c $(LDLIBS) -o $@
anchors: all
	python3 -B scripts/export_anchors.py
$(BUILD)/reference/renderer.c: scripts/derive_renderer.py sources.json vendor/glyphs.upstream.c vendor/botw_xbox_diagram.original.inc | $(BUILD)
	python3 -B scripts/derive_renderer.py --original-front --output $(BUILD)/reference/renderer.c
$(BUILD)/render_reference: example.c $(BUILD)/reference/renderer.c steamdeck_renderer.h renderer_api.inc inclined_view.inc vendor/imstb_truetype.h | $(BUILD)
	$(CC) $(CFLAGS) -I. example.c $(BUILD)/reference/renderer.c $(LDLIBS) -o $@
reference: $(BUILD)/render_reference
	$(BUILD)/render_reference front $(FONT) $(BUILD)/reference/front.rgba
	$(BUILD)/render_reference inclined $(FONT) $(BUILD)/reference/inclined.rgba
	$(BUILD)/render_reference top $(FONT) $(BUILD)/reference/top.rgba
check: all reference
	python3 -B scripts/export_anchors.py --check
	$(BUILD)/test_renderer $(FONT)
	$(BUILD)/render_deck front $(FONT) $(BUILD)/front.rgba
	$(BUILD)/render_deck inclined $(FONT) $(BUILD)/inclined.rgba
	$(BUILD)/render_deck top $(FONT) $(BUILD)/top.rgba
	python3 -B scripts/verify_outputs.py
check-rle: all
	python3 -B scripts/test_rgba_rle.py
clean:
	rm -rf $(BUILD)
