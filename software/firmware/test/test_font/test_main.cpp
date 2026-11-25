// Caption fonts and text rendering against font.py / column_model.py, the pattern generator, the marquee.
#include <unity.h>

#include "captions.h"
#include "povpattern.h"
#include "vec_font.h"

static uint8_t fr[POV_FRAME_PIXELS], fr2[POV_FRAME_PIXELS];
static uint8_t pal[POV_MAX_PAL][3];

void setUp() {}
void tearDown() {}

static void rle_decode_vec(const uint8_t* rle, size_t n, uint8_t* dst) {
  size_t pos = 0;
  for (size_t k = 0; k + 1 < n; k += 2) { memset(dst + pos, rle[k + 1], rle[k]); pos += rle[k]; }
  TEST_ASSERT_EQUAL(POV_FRAME_PIXELS, pos);
}

void test_text_widths_match_python() {
  for (int i = 0; i < VEC_FONT_N; i++) {
    TEST_ASSERT_EQUAL_MESSAGE(VEC_FONT_W5[i], cap::text_width(VEC_FONT_WORDS[i], false), VEC_FONT_WORDS[i]);
    TEST_ASSERT_EQUAL_MESSAGE(VEC_FONT_W7[i], cap::text_width(VEC_FONT_WORDS[i], true), VEC_FONT_WORDS[i]);
  }
}

void test_auto_font_choice_matches_layout_word() {
  for (int i = 0; i < VEC_FONT_N; i++) {
    const char* w = VEC_FONT_WORDS[i];
    bool big = cap::text_width(w, true) <= cap::WIN_W;                 // Captions::draw_word's rule
    bool scroll = !big && cap::text_width(w, false) > cap::WIN_W;
    TEST_ASSERT_EQUAL_MESSAGE(VEC_FONT_BIG[i] != 0, big, w);
    TEST_ASSERT_EQUAL_MESSAGE(VEC_FONT_SCROLL[i] != 0, scroll, w);
  }
}

void test_glyph_coverage() {
  for (char c = 'A'; c <= 'Z'; c++) { TEST_ASSERT_NOT_NULL(cap::glyph(c, false)); TEST_ASSERT_NOT_NULL(cap::glyph(c, true)); }
  for (char c = '0'; c <= '9'; c++) { TEST_ASSERT_NOT_NULL(cap::glyph(c, false)); TEST_ASSERT_NOT_NULL(cap::glyph(c, true)); }
  TEST_ASSERT_NULL(cap::glyph('*', false));
  TEST_ASSERT_NULL(cap::glyph('{', false));
  TEST_ASSERT_NULL(cap::glyph((char)200, true));
  TEST_ASSERT_EQUAL_PTR(cap::glyph('A', false), cap::glyph('a', false));   // lowercase maps to uppercase
  TEST_ASSERT_EQUAL(3, cap::glyph(' ', false)->w);
  TEST_ASSERT_EQUAL(4, cap::glyph(' ', true)->w);
  TEST_ASSERT_EQUAL(0, cap::text_width("", true));
  TEST_ASSERT_EQUAL(0, cap::text_width("*", true));
}

void test_word_mode_frames_match_python() {
  const char* words[2] = {"HI", "HELLO"};
  for (int i = 0; i < 2; i++) {
    cap::Captions c;
    c.begin();
    char msg[64];
    snprintf(msg, sizeof msg, "{\"cap\":\"word\",\"w\":\"%s\"}", words[i]);
    c.receive(msg, strlen(msg));
    c.render(0.0, 1.0 / 30.0, fr);
    rle_decode_vec(VEC_FONT_FRAMES_RLE + VEC_FONT_FRAMES_RLE_OFF[i], VEC_FONT_FRAMES_RLE_OFF[i + 1] - VEC_FONT_FRAMES_RLE_OFF[i], fr2);
    TEST_ASSERT_EQUAL_UINT8_ARRAY_MESSAGE(fr2, fr, POV_FRAME_PIXELS, words[i]);
    // centred in the window
    int lo = 96, hi = -1;
    for (int r = 0; r < POV_ROWS; r++) for (int col = 0; col < POV_COLS; col++) if (fr[r * POV_COLS + col]) { lo = std::min(lo, col); hi = std::max(hi, col); }
    TEST_ASSERT_TRUE(lo >= cap::WIN_L && hi <= cap::WIN_R);
    TEST_ASSERT_TRUE(fabs((lo + hi) / 2.0 - 47.5) <= 1.0);
  }
}

void test_marquee_moves_left_and_wraps() {
  memset(fr, 0, sizeof fr);
  cap::draw_text_marquee(fr, "HI", 0, 96, true, 2, 1);
  int lit = 0;
  for (int p = 0; p < POV_FRAME_PIXELS; p++) lit += fr[p] != 0;
  TEST_ASSERT_TRUE(lit > 20);
  memset(fr2, 0, sizeof fr2);
  cap::draw_text_marquee(fr2, "HI", 1, 96, true, 2, 1);
  // x + 1: every column moves one to the viewer's left (lower column index), wrapping round the drum
  for (int r = 0; r < POV_ROWS; r++)
    for (int col = 0; col < POV_COLS; col++) TEST_ASSERT_EQUAL(fr[r * POV_COLS + (col + 1) % POV_COLS], fr2[r * POV_COLS + col]);
  // at x = 0 the text's first glyph column sits at the window's right edge and the rest is still round the back
  // (columns WIN_R + 1 ...); the column left of the edge is dark
  bool at_edge = false, beyond = false;
  for (int r = 0; r < POV_ROWS; r++) { at_edge |= fr[r * POV_COLS + cap::WIN_R] != 0; beyond |= fr[r * POV_COLS + cap::WIN_R + 1] != 0; }
  TEST_ASSERT_TRUE(at_edge);
  TEST_ASSERT_TRUE(beyond);
  for (int r = 0; r < POV_ROWS; r++) TEST_ASSERT_EQUAL(0, fr[r * POV_COLS + cap::WIN_R - 1]);
}

void test_scroller_state() {
  pat::Scroller s;
  s.set("POV LED COLUMN", 30);
  TEST_ASSERT_TRUE(s.period >= 96);
  int n1 = s.render(1.0 / 30.0, fr, pal);
  TEST_ASSERT_EQUAL(2, n1);
  TEST_ASSERT_DOUBLE_WITHIN(1e-9, 1.0, s.x);
  for (int k = 0; k < 2000; k++) s.render(1.0 / 30.0, fr, pal);
  TEST_ASSERT_TRUE(s.x >= 0 && s.x < s.period);
}

void test_patterns() {
  // row ramp: monotonic bottom to top, identical columns
  TEST_ASSERT_EQUAL(32, pat::rowramp(fr, pal));
  for (int r = 1; r < POV_ROWS; r++) TEST_ASSERT_TRUE(fr[r * POV_COLS] >= fr[(r - 1) * POV_COLS]);
  TEST_ASSERT_TRUE(fr[41 * POV_COLS] > fr[0]);
  for (int r = 0; r < POV_ROWS; r++) for (int c = 1; c < POV_COLS; c++) TEST_ASSERT_EQUAL(fr[r * POV_COLS], fr[r * POV_COLS + c]);
  // sets: row r gets 1 + r % 3
  pat::sets(fr, pal);
  for (int r = 0; r < POV_ROWS; r++) TEST_ASSERT_EQUAL(1 + r % 3, fr[r * POV_COLS + 10]);
  // the F: stem on the left (low columns), bars at the top (high rows); nothing outside the window
  pat::letter_f(fr, pal);
  int lo = 96, hi = -1, rlo = 42, rhi = -1;
  for (int r = 0; r < POV_ROWS; r++) for (int c = 0; c < POV_COLS; c++) if (fr[r * POV_COLS + c]) { lo = std::min(lo, c); hi = std::max(hi, c); rlo = std::min(rlo, r); rhi = std::max(rhi, r); }
  TEST_ASSERT_TRUE(lo >= cap::WIN_L && hi <= cap::WIN_R);
  TEST_ASSERT_TRUE(fr[rhi * POV_COLS + hi]);                 // top-right corner lit (top bar)
  TEST_ASSERT_FALSE(fr[rlo * POV_COLS + hi]);                // bottom-right dark (no bottom bar: it is an F, not an E)
  TEST_ASSERT_TRUE(fr[rlo * POV_COLS + lo]);                 // bottom-left lit (stem)
  // by name
  TEST_ASSERT_EQUAL(0, pat::by_name("nope", fr, pal));
  TEST_ASSERT_TRUE(pat::by_name("grid", fr, pal) > 0);
  TEST_ASSERT_TRUE(pat::by_name("strips", fr, pal) > 0);
  TEST_ASSERT_TRUE(pat::by_name("colramp", fr, pal) > 0);
  TEST_ASSERT_TRUE(pat::by_name("white", fr, pal) > 0);
  for (int p = 0; p < POV_FRAME_PIXELS; p++) TEST_ASSERT_EQUAL(1, fr[p]);
  // every pattern only uses palette indices below its palette size
  const char* names[] = {"rowramp", "colramp", "sets", "grid", "f", "white", "strips"};
  for (int i = 0; i < 7; i++) {
    int n = pat::by_name(names[i], fr, pal);
    for (int p = 0; p < POV_FRAME_PIXELS; p++) TEST_ASSERT_TRUE(fr[p] < n);
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_text_widths_match_python);
  RUN_TEST(test_auto_font_choice_matches_layout_word);
  RUN_TEST(test_glyph_coverage);
  RUN_TEST(test_word_mode_frames_match_python);
  RUN_TEST(test_marquee_moves_left_and_wraps);
  RUN_TEST(test_scroller_state);
  RUN_TEST(test_patterns);
  return UNITY_END();
}
