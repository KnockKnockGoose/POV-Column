// SK9822 frame layout, palette/gamma, the LED current model against povanim.current_profile, and the current cap.
#include <unity.h>

#include "povframe.h"
#include "vec_current.h"
#include "vec_pova.h"

static uint8_t frame[POV_FRAME_PIXELS];
static uint8_t buf[POV_FRAME_BYTES];
static pov::PalBytes pal;
static uint16_t duty[POV_MAX_PAL];

void setUp() {}
void tearDown() {}

void test_cap_matches_the_validator() {
  TEST_ASSERT_EQUAL_DOUBLE(VEC_CAP_MA, (double)pov::CAP_MA);                      // povanim.CAP_MA == firmware CAP_MA
  TEST_ASSERT_EQUAL_DOUBLE(VEC_CUR_FIXED_MA, (double)(pov::IDLE_MA + pov::I_ESP_MA));
}

void test_frame_layout() {
  memset(frame, 0, sizeof frame);
  memset(pal, 0, sizeof pal);
  for (int i = 0; i < POV_MAX_PAL; i++) pal[i][0] = (uint8_t)(0xE0 | (i ? 9 : 0));
  pal[1][1] = 10; pal[1][2] = 20; pal[1][3] = 30;
  frame[5 * POV_COLS + 0] = 1;    // row 5, column 0: LED 5 of strip 0 at scheduler column 0 (even strip: row = 3*i + 0 -> no, row 5 = set B)
  pov::build_column(buf, 0, frame, 0, pal);
  for (int i = 0; i < 4; i++) TEST_ASSERT_EQUAL_HEX8(0x00, buf[i]);                       // start frame
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) TEST_ASSERT_EQUAL_HEX8(0xE0, buf[4 + 4 * k] & 0xE0);   // 111xxxxx
  for (int i = 0; i < 24; i++) TEST_ASSERT_EQUAL_HEX8(0xFF, buf[4 + 4 * POV_LEDS_PER_CHAIN + i]);      // end frame
  for (int i = 0; i < 4; i++) TEST_ASSERT_EQUAL_HEX8(0x00, buf[POV_FRAME_BYTES - 4 + i]);              // zero latch
  // Light the one pixel that strip 2's LED 1 shows at scheduler column 0. Strip 2 sits 2 x 4 = 8 columns ahead, so it
  // shows image column 8. It is an even strip (LED index = k), in interleave set (2 + POV_SET_SHIFT) % 3, so its LED 1
  // shows row 3 * 1 + that set: row 5 in the design numbering (shift 0), row 4 as built (shift 2, since 2026-11-12).
  memset(frame, 0, sizeof frame);
  frame[(3 * 1 + (2 + POV_SET_SHIFT) % 3) * POV_COLS + 8] = 1;
  pov::build_column(buf, 0, frame, 0, pal);
  int lit = 0, where = -1;
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) if (buf[4 + 4 * k + 1] == 10) { lit++; where = k; }
  TEST_ASSERT_EQUAL(1, lit);
  TEST_ASSERT_EQUAL(14 * 2 + 1, where);          // strip 2, LED 1
  TEST_ASSERT_EQUAL_HEX8(0xE0 | 9, buf[4 + 4 * where]);
  TEST_ASSERT_EQUAL_HEX8(20, buf[4 + 4 * where + 2]);
  TEST_ASSERT_EQUAL_HEX8(30, buf[4 + 4 * where + 3]);
}

void test_blank_frame() {
  memset(buf, 0xAA, sizeof buf);
  pov::build_blank(buf);
  for (int i = 0; i < 4; i++) TEST_ASSERT_EQUAL_HEX8(0, buf[i]);
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) {
    TEST_ASSERT_EQUAL_HEX8(0xE0, buf[4 + 4 * k]);
    TEST_ASSERT_EQUAL_HEX8(0, buf[5 + 4 * k]); TEST_ASSERT_EQUAL_HEX8(0, buf[6 + 4 * k]); TEST_ASSERT_EQUAL_HEX8(0, buf[7 + 4 * k]);
  }
  for (int i = 0; i < 24; i++) TEST_ASSERT_EQUAL_HEX8(0xFF, buf[4 + 4 * POV_LEDS_PER_CHAIN + i]);
  for (int i = 0; i < 4; i++) TEST_ASSERT_EQUAL_HEX8(0, buf[POV_FRAME_BYTES - 4 + i]);
}

void test_palette_gamma_and_order() {
  uint8_t rgb[3][3] = {{0, 0, 0}, {255, 128, 10}, {1, 2, 3}};
  pov::make_palette(pal, rgb, 3, 17);
  TEST_ASSERT_EQUAL_HEX8(0xE0, pal[0][0]);
  TEST_ASSERT_EQUAL_HEX8(0xE0 | 17, pal[1][0]);
  TEST_ASSERT_EQUAL_HEX8(POV_GAMMA22[10], pal[1][1]);    // B
  TEST_ASSERT_EQUAL_HEX8(POV_GAMMA22[128], pal[1][2]);   // G
  TEST_ASSERT_EQUAL_HEX8(POV_GAMMA22[255], pal[1][3]);   // R
  TEST_ASSERT_EQUAL_HEX8(255, POV_GAMMA22[255]);
  TEST_ASSERT_EQUAL_HEX8(0, POV_GAMMA22[0]);
  TEST_ASSERT_EQUAL_HEX8(56, POV_GAMMA22[128]);          // round(255 * 0.502^2.2) = 56 (povanim.gamma_lut)
  TEST_ASSERT_EQUAL_HEX8(0xE0, pal[3][0]);               // unused entries are off
  for (int i = 1; i < 256; i++) TEST_ASSERT_TRUE(POV_GAMMA22[i] >= POV_GAMMA22[i - 1]);   // monotonic
}

static void all(uint8_t v) { memset(frame, v, sizeof frame); }

void test_current_model_all_white() {
  uint8_t bw[2][3] = {{0, 0, 0}, {255, 255, 255}};
  pov::palette_duty(bw, 2, duty);
  all(1);
  TEST_ASSERT_EQUAL_UINT32(336 * 60, pov::worst_column_ma(frame, duty, 31));
  TEST_ASSERT_EQUAL_DOUBLE(VEC_CUR_ALLWHITE_GB31_MAX, (double)pov::worst_total_ma(frame, duty, 31));
  TEST_ASSERT_DOUBLE_WITHIN(1.0, VEC_CUR_ALLWHITE_GB15_MAX, (double)pov::worst_total_ma(frame, duty, 15));
  all(0);
  TEST_ASSERT_EQUAL_DOUBLE(VEC_CUR_FIXED_MA, (double)pov::worst_total_ma(frame, duty, 31));
}

void test_current_model_matches_python_on_sparse_and_dog_frames() {
  uint8_t bw[2][3] = {{0, 0, 0}, {255, 255, 255}};
  pov::palette_duty(bw, 2, duty);
  memcpy(frame, VEC_CUR_DIAG, sizeof frame);
  TEST_ASSERT_DOUBLE_WITHIN(0.01 * VEC_CUR_DIAG_GB31_MAX, VEC_CUR_DIAG_GB31_MAX, (double)pov::worst_total_ma(frame, duty, 31));
  // the dog's first frame with its 13-colour palette (gamma LUT rounding vs the exact power: within 1.5 %)
  uint8_t dogpal[POV_MAX_PAL][3];
  memset(dogpal, 0, sizeof dogpal);
  memcpy(dogpal, VEC_DOG_PAL, 3 * VEC_DOG_NPAL);
  pov::palette_duty(dogpal, VEC_DOG_NPAL, duty);
  memcpy(frame, VEC_DOG_F0, sizeof frame);
  TEST_ASSERT_DOUBLE_WITHIN(0.015 * VEC_CUR_DOG0_GB31_MAX, VEC_CUR_DOG0_GB31_MAX, (double)pov::worst_total_ma(frame, duty, 31));
  TEST_ASSERT_DOUBLE_WITHIN(0.015 * VEC_CUR_DOG0_GB8_MAX, VEC_CUR_DOG0_GB8_MAX, (double)pov::worst_total_ma(frame, duty, 8));
  TEST_ASSERT_TRUE(pov::worst_total_ma(frame, duty, 31) < pov::CAP_MA);   // the dog never needs the cap
}

void test_fit_gb() {
  TEST_ASSERT_EQUAL(3, pov::fit_gb(336 * 60, 31, pov::CAP_MA));       // all white: 2264 mA budget / 20160 -> 3
  TEST_ASSERT_EQUAL(31, pov::fit_gb(100, 31, pov::CAP_MA));
  TEST_ASSERT_EQUAL(8, pov::fit_gb(100, 8, pov::CAP_MA));
  TEST_ASSERT_EQUAL(1, pov::fit_gb(1000000, 31, pov::CAP_MA));         // never 0
  TEST_ASSERT_EQUAL(1, pov::fit_gb(10, 31, 100));                      // cap below the idle current: minimum
  // the fitted field really keeps LED + idle under the cap, and one step more would not
  uint32_t drive = 336 * 60;
  uint8_t gb = pov::fit_gb(drive, 31, pov::CAP_MA);
  TEST_ASSERT_TRUE(drive * gb / 31 + pov::IDLE_MA <= pov::CAP_MA);
  TEST_ASSERT_TRUE(drive * (gb + 1) / 31 + pov::IDLE_MA > pov::CAP_MA);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_cap_matches_the_validator);
  RUN_TEST(test_frame_layout);
  RUN_TEST(test_blank_frame);
  RUN_TEST(test_palette_gamma_and_order);
  RUN_TEST(test_current_model_all_white);
  RUN_TEST(test_current_model_matches_python_on_sparse_and_dog_frames);
  RUN_TEST(test_fit_gb);
  return UNITY_END();
}
