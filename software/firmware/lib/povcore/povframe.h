// povframe.h - SK9822 column frames, palettes and the LED current model for the POV LED Column v2.
// Pure functions, no hardware: the firmware (src/main.cpp, src/phase0) and the host tests (test/) share this file.
//
// Frame format per chain (FastLED's SK9822 encoder + one zero latch frame): 4 B start (0x00), per LED 0xE0|gb, B, G, R,
// end frame of (n/32 + 1) DWords of 0xFF, then 4 B of 0x00 so the SK9822 (which latches on the *next* start frame)
// updates every LED now. 168 LEDs -> 4 + 672 + 24 + 4 = 704 B = 5,632 bits = 0.704 ms at 8 MHz.
#pragma once
#include "pov_compat.h"
#include "povgamma.h"
#include "povmap.h"

#define POV_FRAME_BYTES (4 + 4 * POV_LEDS_PER_CHAIN + 4 * (POV_LEDS_PER_CHAIN / 32 + 1) + 4)
#define POV_FRAME_PIXELS (POV_ROWS * POV_COLS)
#define POV_MAX_PAL 32
#define POV_TICK_COLS (POV_COLS / POV_K_PASSES)   // 12 columns = 1/8 revolution = one refresh tick

namespace pov {

// Current model, the same one as povanim.current_profile and column_model._limit: 20 mA per channel at full duty after
// gamma, scaled by the 5-bit field / 31; 1 mA idle per LED; 120 mA for the ESP32 and its radio.
static const uint32_t I_CH_MA = 20, I_DARK_MA = 1, I_ESP_MA = 120;
static const uint32_t N_LEDS = POV_CHAINS * POV_LEDS_PER_CHAIN;            // 336
static const uint32_t IDLE_MA = N_LEDS * I_DARK_MA;                        // 336
// INIU USB-A port label 5 V 3 A (read 2026-11-03): LEDs incl. dark current <= 2,600 mA; the ESP32's 120 mA is on top
// (2.72 A, 9 % under the port rating; F1 is a 4 A fast-blow). Electrical report rev e.
static const uint32_t CAP_MA = 2600;

typedef uint8_t PalBytes[POV_MAX_PAL][4];   // what the LEDs get: 0xE0|gb, B, G, R; entry 0 is always off
typedef uint8_t PalRgb[POV_MAX_PAL][3];     // sRGB 8-bit as stored in a .pova file

static inline int led_strip(int chain, int k) { return POV_LED_COLOFF[chain][k] / POV_COLS_PER_STRIP; }   // 0..23

// Build one chain's SK9822 frame for scheduler column `col` (strip 0 points at image column col). strip_mask: bit s set
// = strip s is lit; a cleared bit blanks that strip's LEDs (front-only mode). Image column of LED k = col + its strip's
// offset (4 columns per 15 deg), mod 96.
static inline void build_column(uint8_t* buf, int chain, const uint8_t* frame, int col, const PalBytes pal,
                                uint32_t strip_mask = 0xFFFFFFu) {
  memset(buf, 0, 4);
  uint8_t* p = buf + 4;
  const uint8_t* row = POV_LED_ROW[chain];
  const uint8_t* off = POV_LED_COLOFF[chain];
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) {
    int c = col + off[k];
    if (c >= POV_COLS) c -= POV_COLS;
    uint8_t idx = frame[row[k] * POV_COLS + c];
    if (!((strip_mask >> (off[k] / POV_COLS_PER_STRIP)) & 1u)) idx = 0;
    const uint8_t* q = pal[idx];
    p[0] = q[0]; p[1] = q[1]; p[2] = q[2]; p[3] = q[3];
    p += 4;
  }
  int endb = 4 * (POV_LEDS_PER_CHAIN / 32 + 1);
  memset(p, 0xFF, endb);
  p += endb;
  memset(p, 0x00, 4);
}

// Every LED off, current field 0
static inline void build_blank(uint8_t* buf) {
  memset(buf, 0, POV_FRAME_BYTES);
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) buf[4 + 4 * k] = 0xE0;
  memset(buf + 4 + 4 * POV_LEDS_PER_CHAIN, 0xFF, 4 * (POV_LEDS_PER_CHAIN / 32 + 1));
}

// Gamma + colour order + current field for a palette. Entry 0 is forced off; unused entries are off too.
static inline void make_palette(PalBytes out, const uint8_t (*rgb)[3], int npal, uint8_t gb) {
  for (int i = 0; i < POV_MAX_PAL; i++) {
    bool on = i > 0 && i < npal;
    out[i][0] = 0xE0 | (on ? (gb & 31) : 0);
    out[i][1] = on ? POV_GAMMA22[rgb[i][2]] : 0;   // B
    out[i][2] = on ? POV_GAMMA22[rgb[i][1]] : 0;   // G
    out[i][3] = on ? POV_GAMMA22[rgb[i][0]] : 0;   // R
  }
}

// Per palette entry: sum of the three gamma-corrected 8-bit duties (0..765). 20 mA x duty/255 x gb/31 is the LED current.
static inline void palette_duty(const uint8_t (*rgb)[3], int npal, uint16_t duty[POV_MAX_PAL]) {
  for (int i = 0; i < POV_MAX_PAL; i++)
    duty[i] = (i > 0 && i < npal) ? (uint16_t)(POV_GAMMA22[rgb[i][0]] + POV_GAMMA22[rgb[i][1]] + POV_GAMMA22[rgb[i][2]]) : 0;
}

// Worst of the 96 rotor positions: LED drive current in mA (no idle, no ESP32) at current field gb. ~32k lookups.
static inline uint32_t worst_column_ma(const uint8_t* frame, const uint16_t duty[POV_MAX_PAL], uint8_t gb) {
  uint32_t worst = 0;
  for (int col = 0; col < POV_COLS; col++) {
    uint32_t sum = 0;
    for (int ch = 0; ch < POV_CHAINS; ch++) {
      const uint8_t* row = POV_LED_ROW[ch];
      const uint8_t* off = POV_LED_COLOFF[ch];
      for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) {
        int c = col + off[k];
        if (c >= POV_COLS) c -= POV_COLS;
        sum += duty[frame[row[k] * POV_COLS + c]];
      }
    }
    if (sum > worst) worst = sum;
  }
  return (uint32_t)(((uint64_t)worst * I_CH_MA * gb) / (255u * 31u));
}

// The same number in the reference model's units: LED drive + idle + ESP32 (povanim.current_profile(...).max())
static inline uint32_t worst_total_ma(const uint8_t* frame, const uint16_t duty[POV_MAX_PAL], uint8_t gb) {
  return worst_column_ma(frame, duty, gb) + IDLE_MA + I_ESP_MA;
}

// Largest current field <= gb_req that keeps (LED drive + idle) under cap_ma, given the drive at gb 31. Never below 1.
static inline uint8_t fit_gb(uint32_t drive_ma_at_31, uint8_t gb_req, uint32_t cap_ma, uint32_t idle_ma = IDLE_MA) {
  uint8_t gb = gb_req > 31 ? 31 : gb_req;
  if (cap_ma <= idle_ma) return 1;
  uint32_t budget = cap_ma - idle_ma;
  while (gb > 1 && drive_ma_at_31 * gb > budget * 31) gb--;
  return gb;
}

// Front-only mode: strip s sits at 3.75 * k + 15 * s degrees from the hall reference when the scheduler is at column
// index k. A strip is "front" when it is within 90 degrees of front_deg; the mask has bit s set for front strips.
static inline uint32_t front_mask(int k, int front_deg) {
  uint32_t m = 0;
  for (int s = 0; s < POV_STRIPS; s++) {
    // angles in 1/4 degree to stay in integers: column = 15 quarter-degrees, strip = 60
    int a = (k * 15 + s * 60 - front_deg * 4) % 1440;
    if (a < 0) a += 1440;
    if (a > 720) a = 1440 - a;
    if (a <= 360) m |= 1u << s;
  }
  return m;
}

}  // namespace pov
