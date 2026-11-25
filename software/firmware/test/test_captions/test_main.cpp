// The caption mode (captions.h) replayed tick by tick against column_model.ColumnCaptions: the same JSON messages at
// the same ticks must give the same 42 x 96 frame (CRC per tick, full frames at event ticks), the same tape position,
// speed, current field, drops and mode.
#include <unity.h>

#include "captions.h"
#include "pova.h"            // pova_crc32 (zlib CRC-32, the same function gen_vectors.py used)
#include "vec_captions.h"

static uint8_t fr[POV_FRAME_PIXELS], fr2[POV_FRAME_PIXELS];

void setUp() {}
void tearDown() {}

static void rle_decode_vec(const uint8_t* rle, size_t n, uint8_t* dst) {
  size_t pos = 0;
  for (size_t k = 0; k + 1 < n; k += 2) { memset(dst + pos, rle[k + 1], rle[k]); pos += rle[k]; }
  TEST_ASSERT_EQUAL(POV_FRAME_PIXELS, pos);
}

struct Session {
  const char* name;
  const VecCapEvent* events;
  int ticks, mode0, nkeep;
  const uint32_t* crc;
  const int* keep;
  const uint8_t* rle;
  const uint32_t* rle_off;
  const double *x, *v, *peak;
  const uint8_t *gb, *tickmode;
  const uint32_t* dropped;
};

#define SESSION(N) { #N, VEC_CAP_##N##_EVENTS, VEC_CAP_##N##_TICKS, VEC_CAP_##N##_MODE0, VEC_CAP_##N##_NKEEP, VEC_CAP_##N##_CRC, \
                     VEC_CAP_##N##_KEEP, VEC_CAP_##N##_RLE, VEC_CAP_##N##_RLE_OFF, VEC_CAP_##N##_X, VEC_CAP_##N##_V, \
                     VEC_CAP_##N##_PEAK, VEC_CAP_##N##_GB, VEC_CAP_##N##_TICKMODE, VEC_CAP_##N##_DROPPED }

static const Session SESSIONS[] = { SESSION(WORD), SESSION(HYBRID), SESSION(CRAWL), SESSION(LIMIT), SESSION(CFG) };

// Replays like Python: receive the tick's messages, then one tick render (dt = tick length)
static void replay(const Session& s) {
  cap::Captions c;
  c.begin();
  c.cfg.cap_ma = (uint16_t)VEC_CAP_DEFAULT_CAP_MA;        // the Python Config default (2000 mA incl. idle + ESP32)
  if (s.mode0) c.receive("{\"cap\":\"mode\",\"m\":\"tick\"}", 25);
  int ei = 0, ki = 0;
  char msg[160];
  double tprev = 0;
  for (int k = 0; k < s.ticks; k++) {
    while (s.events[ei].tick == k) { c.receive(s.events[ei].json, strlen(s.events[ei].json)); ei++; }
    // column_model.tick(t): dt = t - previous t (not a constant), so the doubles match bit for bit
    double tk = k * VEC_CAP_TICK_S;
    double dt = tk > tprev ? tk - tprev : VEC_CAP_TICK_S;
    tprev = tk;
    c.render(tk, dt, fr);
    snprintf(msg, sizeof msg, "%s tick %d", s.name, k);
    TEST_ASSERT_EQUAL_MESSAGE(s.tickmode[k] != 0, c.is_tick(), msg);
    TEST_ASSERT_DOUBLE_WITHIN_MESSAGE(1e-6, s.x[k], c.x_pos(), msg);
    TEST_ASSERT_DOUBLE_WITHIN_MESSAGE(1e-6 * (1 + fabs(s.v[k])), s.v[k], c.v_cps(), msg);
    TEST_ASSERT_EQUAL_MESSAGE(s.gb[k], c.gb, msg);
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(s.dropped[k], c.dropped, msg);
    TEST_ASSERT_DOUBLE_WITHIN_MESSAGE(0.5, s.peak[k], c.peak_ma, msg);
    uint32_t crc = pova_crc32(fr, POV_FRAME_PIXELS);
    if (crc != s.crc[k]) {                               // diagnostics before the assertion stops the test
      printf("MISMATCH %s tick %d: x=%.6f v=%.3f tape_end=%d ntape=%d\n", s.name, k, c.x_pos(), c.v_cps(), (int)c.tape_end_col(), c.tape_len());
      for (int i = 0; i < c.tape_len(); i++) {
        const cap::TapeWord* w = c.tape_at(i);
        printf("  [%d] %-12s start=%d width=%d entered=%d t_append=%.4f\n", i, w->text, (int)w->start, (int)w->width, (int)w->entered, w->t_append);
      }
      for (int r = POV_ROWS - 1; r >= 0; r--) {
        bool any = false;
        for (int col = 0; col < POV_COLS; col++) any |= fr[r * POV_COLS + col] != 0;
        if (!any) continue;
        printf("  row %2d: ", r);
        for (int col = 0; col < POV_COLS; col++) putchar(fr[r * POV_COLS + col] ? '#' : '.');
        putchar('\n');
      }
    }
    if (ki < s.nkeep && s.keep[ki] == k) {               // a full frame is stored: compare pixel by pixel first
      rle_decode_vec(s.rle + s.rle_off[ki], s.rle_off[ki + 1] - s.rle_off[ki], fr2);
      TEST_ASSERT_EQUAL_UINT8_ARRAY_MESSAGE(fr2, fr, POV_FRAME_PIXELS, msg);
      ki++;
    }
    TEST_ASSERT_EQUAL_HEX32_MESSAGE(s.crc[k], crc, msg);
  }
  TEST_ASSERT_EQUAL(-1, s.events[ei].tick);               // every event was consumed
}

void test_word_session() { replay(SESSIONS[0]); }
void test_hybrid_ticker_session() { replay(SESSIONS[1]); }
void test_crawl_ticker_session() { replay(SESSIONS[2]); }
void test_current_limiter_session() { replay(SESSIONS[3]); }
void test_cfg_session() { replay(SESSIONS[4]); }

// The ESP32 path: a message wake renders at once (dt = 0). In hybrid ticker mode the new word jumps fully into the
// window on that render; in word mode the word shows at once; nothing else moves until the next tick.
void test_message_wake_renders_immediately() {
  cap::Captions c;
  c.begin();
  c.receive("{\"cap\":\"mode\",\"m\":\"tick\"}", 25);
  c.render(0.0, 1.0 / 30.0, fr);
  TEST_ASSERT_TRUE(c.is_tick());
  TEST_ASSERT_EQUAL(0, c.tape_len());
  const char* m = "{\"cap\":\"tick\",\"append\":\"HELLO \",\"id\":7}";
  c.receive(m, strlen(m));
  c.render(0.01, 0.0, fr);                                  // message wake
  TEST_ASSERT_EQUAL(1, c.tape_len());
  TEST_ASSERT_EQUAL(1, c.n_applied);
  TEST_ASSERT_EQUAL_UINT32(7, c.applied_ids[0]);
  int w = cap::text_width("HELLO", false);
  TEST_ASSERT_DOUBLE_WITHIN(1e-9, (double)w, c.x_pos());   // jumped so the word is fully inside the window
  int lo = 96, hi = -1;
  for (int r = 0; r < POV_ROWS; r++) for (int col = 0; col < POV_COLS; col++) if (fr[r * POV_COLS + col]) { lo = std::min(lo, col); hi = std::max(hi, col); }
  TEST_ASSERT_EQUAL(cap::WIN_R - 1, hi);                   // column_model: x = start + width puts the last glyph column at WIN_R - 1
  TEST_ASSERT_EQUAL(cap::WIN_R - w, lo);
  // a second message wake with nothing new changes nothing; a tick within the idle time does not move it either
  memcpy(fr2, fr, sizeof fr);
  c.render(0.02, 0.0, fr);
  TEST_ASSERT_EQUAL_UINT8_ARRAY(fr2, fr, POV_FRAME_PIXELS);
  c.render(1.0 / 30.0, 1.0 / 30.0, fr);
  TEST_ASSERT_EQUAL_UINT8_ARRAY(fr2, fr, POV_FRAME_PIXELS);
  TEST_ASSERT_EQUAL(0, c.n_applied);
  // word mode: the word is drawn on the message wake
  const char* m2 = "{\"cap\":\"mode\",\"m\":\"word\"}";
  const char* m3 = "{\"cap\":\"word\",\"w\":\"HI\",\"id\":9}";
  c.receive(m2, strlen(m2));
  c.receive(m3, strlen(m3));
  c.render(0.05, 0.0, fr);
  int lit = 0;
  for (int p = 0; p < POV_FRAME_PIXELS; p++) lit += fr[p] != 0;
  TEST_ASSERT_TRUE(lit > 20);
  TEST_ASSERT_EQUAL(1, c.n_applied);
  TEST_ASSERT_EQUAL_UINT32(9, c.applied_ids[0]);
}

void test_parser_ignores_garbage_and_queue_overflow_drops() {
  cap::Captions c;
  c.begin();
  c.receive("not json", 8);
  c.receive("{\"cap\":\"nope\"}", 14);
  c.receive("{\"nocap\":1}", 11);
  c.render(0.0, 1.0 / 30.0, fr);
  for (int p = 0; p < POV_FRAME_PIXELS; p++) TEST_ASSERT_EQUAL(0, fr[p]);
  // 40 words queued before a render: the ring holds 15, the rest are dropped, the engine keeps running
  for (int i = 0; i < 40; i++) { char m[48]; snprintf(m, sizeof m, "{\"cap\":\"word\",\"w\":\"W%d\"}", i); c.receive(m, strlen(m)); }
  c.render(1.0 / 30.0, 1.0 / 30.0, fr);
  int lit = 0;
  for (int p = 0; p < POV_FRAME_PIXELS; p++) lit += fr[p] != 0;
  TEST_ASSERT_TRUE(lit > 0);
  // cfg clamps
  c.receive("{\"cap\":\"cfg\",\"gb_max\":99,\"word_vs\":9,\"cap_ma\":1}", 48);
  TEST_ASSERT_EQUAL(31, c.cfg.gb_max);
  TEST_ASSERT_EQUAL(4, c.cfg.word_vs);
  TEST_ASSERT_EQUAL(500, c.cfg.cap_ma);
}

void test_palette_rgb_truncates_dim_like_python() {
  cap::Captions c;
  uint8_t p[3][3];
  c.palette_rgb(p);
  TEST_ASSERT_EQUAL(0, p[0][0]);
  TEST_ASSERT_EQUAL(255, p[1][0]); TEST_ASSERT_EQUAL(214, p[1][1]); TEST_ASSERT_EQUAL(160, p[1][2]);
  TEST_ASSERT_EQUAL(76, p[2][0]);   // int(255 * 0.3)
  TEST_ASSERT_EQUAL(64, p[2][1]);   // int(214 * 0.3)
  TEST_ASSERT_EQUAL(48, p[2][2]);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_word_session);
  RUN_TEST(test_hybrid_ticker_session);
  RUN_TEST(test_crawl_ticker_session);
  RUN_TEST(test_current_limiter_session);
  RUN_TEST(test_cfg_session);
  RUN_TEST(test_message_wake_renders_immediately);
  RUN_TEST(test_parser_ignores_garbage_and_queue_overflow_drops);
  RUN_TEST(test_palette_rgb_truncates_dim_like_python);
  return UNITY_END();
}
