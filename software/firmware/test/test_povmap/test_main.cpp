// LED -> (row, column offset) mapping: the generated tables against a brute-force re-derivation, against the Python
// reference vectors (povanim.column_indices), and against the simulator's paint model (povsim.simulate.paint_times),
// so the simulator and the firmware agree pixel for pixel.
#include <unity.h>

#include "povframe.h"
#include "vec_povmap.h"

static uint8_t frame[POV_FRAME_PIXELS];
static uint8_t buf[POV_FRAME_BYTES];
static pov::PalBytes pal;

void setUp() {}
void tearDown() {}

static void fill_frame() {
  for (int r = 0; r < POV_ROWS; r++)
    for (int c = 0; c < POV_COLS; c++) frame[r * POV_COLS + c] = (uint8_t)((r * POV_COLS + c) % 251);
}

// a synthetic palette with distinct bytes per index (only indices < 32 are valid palette entries)
static void fill_pal() {
  for (int i = 0; i < POV_MAX_PAL; i++) {
    pal[i][0] = (uint8_t)(0xE0 | (i ? 31 : 0));
    pal[i][1] = (uint8_t)i;
    pal[i][2] = (uint8_t)((i * 7) & 255);
    pal[i][3] = (uint8_t)((i * 13) & 255);
  }
}

// strip s, LED i (index along the data direction) -> chain, position, row, column offset (povanim.py)
static int strip_of(int chain, int pos) { return chain * (POV_STRIPS / POV_CHAINS) + pos / (POV_LEDS_PER_CHAIN / (POV_STRIPS / POV_CHAINS)); }

void test_constants() {
  TEST_ASSERT_EQUAL(42, POV_ROWS);
  TEST_ASSERT_EQUAL(96, POV_COLS);
  TEST_ASSERT_EQUAL(2, POV_CHAINS);
  TEST_ASSERT_EQUAL(168, POV_LEDS_PER_CHAIN);
  TEST_ASSERT_EQUAL(24, POV_STRIPS);
  TEST_ASSERT_EQUAL(4, POV_COLS_PER_STRIP);
  TEST_ASSERT_EQUAL(8, POV_K_PASSES);
  TEST_ASSERT_EQUAL(704, POV_FRAME_BYTES);
  TEST_ASSERT_EQUAL(12, POV_TICK_COLS);
}

void test_tables_match_brute_force() {
  const int lps = 14;
  for (int chain = 0; chain < POV_CHAINS; chain++)
    for (int pos = 0; pos < POV_LEDS_PER_CHAIN; pos++) {
      int s = chain * 12 + pos / lps;
      int i = pos % lps;
      int k = (s % 2 == 0) ? i : (lps - 1 - i);     // odd strips are mounted upside down (data in at the top)
      int row = 3 * k + (s + POV_SET_SHIFT) % 3;      // three interleaved sets A/B/C (as-built rail shift)
      int off = 4 * s;                                // 15 deg per strip = 4 columns
      TEST_ASSERT_EQUAL_MESSAGE(row, POV_LED_ROW[chain][pos], "row");
      TEST_ASSERT_EQUAL_MESSAGE(off, POV_LED_COLOFF[chain][pos], "column offset");
      TEST_ASSERT_EQUAL(s, pov::led_strip(chain, pos));
      TEST_ASSERT_EQUAL(s, strip_of(chain, pos));
    }
}

void test_every_row_has_eight_leds_twelve_columns_apart() {
  for (int r = 0; r < POV_ROWS; r++) {
    int offs[8], n = 0;
    for (int chain = 0; chain < POV_CHAINS; chain++)
      for (int pos = 0; pos < POV_LEDS_PER_CHAIN; pos++)
        if (POV_LED_ROW[chain][pos] == r) { TEST_ASSERT_TRUE(n < 8); offs[n++] = POV_LED_COLOFF[chain][pos]; }
    TEST_ASSERT_EQUAL(8, n);
    std::sort(offs, offs + 8);
    for (int i = 1; i < 8; i++) TEST_ASSERT_EQUAL(12, offs[i] - offs[i - 1]);
  }
}

void test_column_indices_match_python() {
  fill_frame();
  const uint8_t* vec[4] = {VEC_MAP_COL_0, VEC_MAP_COL_1, VEC_MAP_COL_2, VEC_MAP_COL_3};
  for (int i = 0; i < 4; i++) {
    int col = VEC_MAP_COLS[i];
    for (int chain = 0; chain < POV_CHAINS; chain++)
      for (int pos = 0; pos < POV_LEDS_PER_CHAIN; pos++) {
        int c = (col + POV_LED_COLOFF[chain][pos]) % POV_COLS;
        uint8_t mine = frame[POV_LED_ROW[chain][pos] * POV_COLS + c];
        TEST_ASSERT_EQUAL(vec[i][chain * POV_LEDS_PER_CHAIN + pos], mine);
      }
  }
}

void test_build_column_matches_python_vectors() {
  fill_frame();
  for (int p = 0; p < POV_FRAME_PIXELS; p++) frame[p] %= POV_MAX_PAL;   // palette-sized indices, same pointwise map
  fill_pal();
  const uint8_t* vec[4] = {VEC_MAP_COL_0, VEC_MAP_COL_1, VEC_MAP_COL_2, VEC_MAP_COL_3};
  for (int i = 0; i < 4; i++)
    for (int chain = 0; chain < POV_CHAINS; chain++) {
      pov::build_column(buf, chain, frame, VEC_MAP_COLS[i], pal);
      for (int pos = 0; pos < POV_LEDS_PER_CHAIN; pos++) {
        uint8_t idx = (uint8_t)(vec[i][chain * POV_LEDS_PER_CHAIN + pos] % POV_MAX_PAL);
        const uint8_t* led = buf + 4 + 4 * pos;
        TEST_ASSERT_EQUAL_HEX8(pal[idx][0], led[0]);
        TEST_ASSERT_EQUAL_HEX8(pal[idx][1], led[1]);
        TEST_ASSERT_EQUAL_HEX8(pal[idx][2], led[2]);
        TEST_ASSERT_EQUAL_HEX8(pal[idx][3], led[3]);
      }
    }
}

// simulate.py: column c of row r (set r % 3) is painted by strip s = (r % 3) + 3 m when strip 0 points at scheduler
// column j = (c - 4 s) mod 96. The firmware must put frame[r][c] on exactly that strip's LED at that moment.
void test_simulator_paint_model_agrees_with_build_column() {
  fill_frame();
  for (int p = 0; p < POV_FRAME_PIXELS; p++) frame[p] %= POV_MAX_PAL;
  fill_pal();
  for (int r = 0; r < POV_ROWS; r++)
    for (int c = 0; c < POV_COLS; c += 5)
      for (int m = 0; m < 8; m++) {
        int s = ((r - POV_SET_SHIFT) % 3 + 3) % 3 + 3 * m;
        int j = ((c - 4 * s) % POV_COLS + POV_COLS) % POV_COLS;
        int chain = s / 12;
        int k = (r - (s + POV_SET_SHIFT) % 3) / 3;                      // LED k of the strip's data order after the odd-strip inversion
        int i = (s % 2 == 0) ? k : 13 - k;
        int pos = 14 * (s % 12) + i;
        TEST_ASSERT_EQUAL(r, POV_LED_ROW[chain][pos]);
        pov::build_column(buf, chain, frame, j, pal);
        uint8_t expect = frame[r * POV_COLS + c];
        const uint8_t* led = buf + 4 + 4 * pos;
        TEST_ASSERT_EQUAL_HEX8(pal[expect][1], led[1]);
        TEST_ASSERT_EQUAL_HEX8(pal[expect][2], led[2]);
        TEST_ASSERT_EQUAL_HEX8(pal[expect][3], led[3]);
      }
}

void test_front_mask_blanks_the_back_half() {
  // scheduler column 0, viewer at 0 deg: strips 0..6 (0..90 deg) and 18..23 (270..345 deg) face the front
  uint32_t m = pov::front_mask(0, 0);
  int n = 0;
  for (int s = 0; s < POV_STRIPS; s++) {
    bool front = (m >> s) & 1u;
    bool expect = (s <= 6) || (s >= 18);
    TEST_ASSERT_EQUAL_MESSAGE(expect, front, "strip front/back at k=0");
    n += front;
  }
  TEST_ASSERT_EQUAL(13, n);
  // half a revolution later the opposite strips face the viewer
  uint32_t m2 = pov::front_mask(48, 0);
  for (int s = 0; s < POV_STRIPS; s++) TEST_ASSERT_EQUAL((s >= 6 && s <= 18), (m2 >> s) & 1u);
  // a blanked strip's LEDs carry current field 0 and black
  fill_frame();
  for (int p = 0; p < POV_FRAME_PIXELS; p++) frame[p] = (uint8_t)(1 + frame[p] % 30);
  fill_pal();
  pov::build_column(buf, 0, frame, 0, pal, m);
  for (int pos = 0; pos < POV_LEDS_PER_CHAIN; pos++) {
    int s = pov::led_strip(0, pos);
    const uint8_t* led = buf + 4 + 4 * pos;
    if ((m >> s) & 1u) TEST_ASSERT_EQUAL_HEX8(0xFF, led[0]);
    else { TEST_ASSERT_EQUAL_HEX8(0xE0, led[0]); TEST_ASSERT_EQUAL_HEX8(0, led[1]); TEST_ASSERT_EQUAL_HEX8(0, led[2]); TEST_ASSERT_EQUAL_HEX8(0, led[3]); }
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_constants);
  RUN_TEST(test_tables_match_brute_force);
  RUN_TEST(test_every_row_has_eight_leds_twelve_columns_apart);
  RUN_TEST(test_column_indices_match_python);
  RUN_TEST(test_build_column_matches_python_vectors);
  RUN_TEST(test_simulator_paint_model_agrees_with_build_column);
  RUN_TEST(test_front_mask_blanks_the_back_half);
  return UNITY_END();
}
