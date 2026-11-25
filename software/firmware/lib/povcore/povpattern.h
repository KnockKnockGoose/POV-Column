// povpattern.h - calibration patterns and the text scroller, drawn as 42 x 96 palette-index frames with their own
// palettes (software report 4, "Calibration patterns"; QA review M7). Phase 2 of the bring-up uses these: the row ramp
// must be monotonic (interleave + odd-strip inversion right), columns must line up across the 24 strips, the "F" must
// be upright and not mirrored.
#pragma once
#include "pov_compat.h"
#include "captions.h"
#include "povframe.h"

namespace pat {

static const int ROWS = POV_ROWS, COLS = POV_COLS;

// Fills pal[0..npal) and returns npal. Index 0 is always off.
static inline int grey_palette(uint8_t pal[POV_MAX_PAL][3], int levels) {
  int n = pov::clampv(levels, 1, POV_MAX_PAL - 1);
  memset(pal, 0, 3 * POV_MAX_PAL);
  for (int i = 1; i <= n; i++) { uint8_t v = (uint8_t)(255 * i / n); pal[i][0] = pal[i][1] = pal[i][2] = v; }
  return n + 1;
}

// "rowramp": brightness rises from row 0 (bottom) to row 41 (top) in 31 grey steps, the same at every column
static inline int rowramp(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  int npal = grey_palette(pal, 31);
  for (int r = 0; r < ROWS; r++) {
    uint8_t ci = (uint8_t)(1 + r * 30 / (ROWS - 1));
    memset(fr + r * COLS, ci, COLS);
  }
  return npal;
}

// "colramp": brightness rises around the drum from column 0 (the hall reference) to 95, every 8th column marked white
static inline int colramp(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  int npal = grey_palette(pal, 30);
  pal[31][0] = 255; pal[31][1] = 255; pal[31][2] = 255;
  npal = 32;
  for (int r = 0; r < ROWS; r++)
    for (int c = 0; c < COLS; c++) fr[r * COLS + c] = (c % 8 == 0) ? 31 : (uint8_t)(1 + c * 29 / (COLS - 1));
  return npal;
}

// "sets": the three interleave sets A/B/C (row mod 3) in red / green / blue, so a strip in the wrong set shows
static inline int sets(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  memset(pal, 0, 3 * POV_MAX_PAL);
  pal[1][0] = 255; pal[2][1] = 255; pal[3][2] = 255;
  for (int r = 0; r < ROWS; r++) memset(fr + r * COLS, 1 + r % 3, COLS);
  return 4;
}

// "grid": every 8th column and every 7th row, plus column 0 and row 0 in a second colour (alignment + direction)
static inline int grid(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  memset(pal, 0, 3 * POV_MAX_PAL);
  pal[1][0] = 90; pal[1][1] = 90; pal[1][2] = 90;
  pal[2][0] = 255; pal[2][1] = 60; pal[2][2] = 0;
  memset(fr, 0, ROWS * COLS);
  for (int r = 0; r < ROWS; r++)
    for (int c = 0; c < COLS; c++) {
      uint8_t ci = 0;
      if (c % 8 == 0 || r % 7 == 0) ci = 1;
      if (c == 0 || r == 0) ci = 2;
      fr[r * COLS + c] = ci;
    }
  return 3;
}

// "f": a big upright F in the viewer's window (columns 32..63), 3-pixel strokes; a mirrored or rotated picture is a
// software trim (dir / offset_x8), not wiring
static inline int letter_f(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  memset(pal, 0, 3 * POV_MAX_PAL);
  pal[1][0] = 255; pal[1][1] = 255; pal[1][2] = 255;
  memset(fr, 0, ROWS * COLS);
  const int c0 = 40, r0 = 6, h = 30, w = 16, s = 3;
  for (int r = r0; r < r0 + h; r++)
    for (int c = c0; c < c0 + w; c++) {
      bool stem = c < c0 + s;
      bool top = r >= r0 + h - s;
      bool mid = r >= r0 + h / 2 - 1 && r < r0 + h / 2 - 1 + s && c < c0 + w - 5;
      if (stem || top || mid) fr[r * COLS + c] = 1;
    }
  return 2;
}

// "white": every pixel lit (the dense current-cap test; the per-frame cap scales the current field)
static inline int white(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  memset(pal, 0, 3 * POV_MAX_PAL);
  pal[1][0] = 255; pal[1][1] = 255; pal[1][2] = 255;
  memset(fr, 1, ROWS * COLS);
  return 2;
}

// "strips": image column 4*s (where strip s sits when strip 0 is at the hall reference) lit in a colour that cycles
// per strip; on the spinning rotor this shows 24 evenly spaced lines, each painted by every strip in turn
static inline int strips(uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  memset(pal, 0, 3 * POV_MAX_PAL);
  static const uint8_t hues[6][3] = {{255, 0, 0}, {255, 160, 0}, {0, 255, 0}, {0, 255, 255}, {0, 0, 255}, {255, 0, 255}};
  for (int i = 0; i < 6; i++) { pal[1 + i][0] = hues[i][0]; pal[1 + i][1] = hues[i][1]; pal[1 + i][2] = hues[i][2]; }
  memset(fr, 0, ROWS * COLS);
  for (int s = 0; s < POV_STRIPS; s++)
    for (int r = 0; r < ROWS; r++) fr[r * COLS + (s * POV_COLS_PER_STRIP) % COLS] = (uint8_t)(1 + s % 6);
  return 7;
}

// Text scroller state (POST /api/text): a marquee around the drum at a fixed speed, built on the caption fonts.
struct Scroller {
  char text[96] = "";
  uint8_t rgb[3] = {255, 214, 160};
  bool big = true;
  uint8_t vs = 2;
  double speed = 30;      // columns per second (30 = 1 column per tick at 225 rpm: the camera-legible crawl)
  double x = 0;           // tape position in columns
  int period = COLS;      // repeat length
  void set(const char* s, double cps) {
    pov::strlcpy_(text, s, sizeof text);
    speed = cps;
    x = 0;
    int w = cap::text_width(text, big);
    period = std::max(COLS, w + 24);
  }
  // advance by dt seconds and draw; palette: 1 = the text colour
  int render(double dt, uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
    memset(pal, 0, 3 * POV_MAX_PAL);
    pal[1][0] = rgb[0]; pal[1][1] = rgb[1]; pal[1][2] = rgb[2];
    x += speed * dt;
    if (x >= period) x -= period * floor(x / period);
    memset(fr, 0, ROWS * COLS);
    cap::draw_text_marquee(fr, text, (int)floor(x), period, big, vs, 1);
    return 2;
  }
};

// Pattern by name; returns the palette size or 0 if unknown
static inline int by_name(const char* name, uint8_t* fr, uint8_t pal[POV_MAX_PAL][3]) {
  if (!strcmp(name, "rowramp")) return rowramp(fr, pal);
  if (!strcmp(name, "colramp")) return colramp(fr, pal);
  if (!strcmp(name, "sets")) return sets(fr, pal);
  if (!strcmp(name, "grid")) return grid(fr, pal);
  if (!strcmp(name, "f")) return letter_f(fr, pal);
  if (!strcmp(name, "white")) return white(fr, pal);
  if (!strcmp(name, "strips")) return strips(fr, pal);
  return 0;
}

static const char* const NAMES = "rowramp colramp sets grid f white strips";

}  // namespace pat
