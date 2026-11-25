// Hall period estimate + column scheduler with synthetic pulse times: 225 rpm = 266,667 us per revolution,
// 96 columns of 2,778 us, re-anchoring at every pulse, bounce lockout, spin-up gate, blank-when-stopped.
#include <unity.h>

#include "povsched.h"

using namespace pov;

static const int64_t T225 = 266667;   // us
static const uint32_t SPI_US = 704, BUILD_US = 40, SLACK_US = 100;

void setUp() {}
void tearDown() {}

static Hall hall;
static SchedCfg cfg;

static void reset() { hall = Hall(); cfg = SchedCfg(); }

void test_config_defaults() {
  SchedCfg c;
  TEST_ASSERT_EQUAL_UINT32(96, c.cols);
  TEST_ASSERT_EQUAL_UINT32(21600, c.lockout_us);     // quarter of the fastest plausible revolution (694 rpm)
  TEST_ASSERT_EQUAL_UINT32(1200000, c.rev_us_max);   // 50 rpm (bench 2026-11-20)
  TEST_ASSERT_EQUAL_UINT32(1500000, c.no_pulse_us);
  TEST_ASSERT_EQUAL_UINT32(15, c.agree_pct);
}

void test_first_pulse_only_anchors_and_two_agreeing_periods_validate() {
  reset();
  int64_t t0 = 5000000;                               // 5 s after boot (QA B1c: the old code took this as the period)
  TEST_ASSERT_TRUE(hall_pulse(hall, cfg, t0));
  HallSnap s = snapshot(hall);
  TEST_ASSERT_EQUAL(t0, s.t);
  TEST_ASSERT_EQUAL_UINT32(0, s.rev_us);
  TEST_ASSERT_FALSE(s.valid);
  TEST_ASSERT_TRUE(should_blank(s, cfg, t0 + 1000));
  TEST_ASSERT_TRUE(hall_pulse(hall, cfg, t0 + T225));
  s = snapshot(hall);
  TEST_ASSERT_EQUAL_UINT32((uint32_t)T225, s.rev_us);
  TEST_ASSERT_FALSE(s.valid);                         // one period is not enough
  TEST_ASSERT_EQUAL(1, s.agree);
  TEST_ASSERT_TRUE(hall_pulse(hall, cfg, t0 + 2 * T225 + 1000));   // +0.4 %: agrees
  s = snapshot(hall);
  TEST_ASSERT_TRUE(s.valid);
  TEST_ASSERT_EQUAL(2, s.agree);
  TEST_ASSERT_UINT32_WITHIN(300, (uint32_t)T225 + 250, s.rev_us);  // IIR alpha 1/4 of the 1000 us step
  TEST_ASSERT_FALSE(should_blank(s, cfg, t0 + 2 * T225 + 2000));
  TEST_ASSERT_EQUAL_UINT32(3, s.pulses);
}

void test_bounce_is_rejected_and_changes_nothing() {
  reset();
  int64_t t0 = 1000000;
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  HallSnap before = snapshot(hall);
  TEST_ASSERT_FALSE(hall_pulse(hall, cfg, t0 + 2 * T225 + 5000));     // 5 ms later: bounce
  TEST_ASSERT_FALSE(hall_pulse(hall, cfg, t0 + 2 * T225 + 21000));    // just inside the lockout
  HallSnap after = snapshot(hall);
  TEST_ASSERT_EQUAL(before.t, after.t);
  TEST_ASSERT_EQUAL_UINT32(before.rev_us, after.rev_us);
  TEST_ASSERT_EQUAL_UINT32(before.pulses, after.pulses);
  TEST_ASSERT_EQUAL_UINT32(2, after.rejected);
  TEST_ASSERT_TRUE(after.valid);
}

void test_blank_when_stopped_or_too_slow() {
  reset();
  int64_t t0 = 1000000;
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  HallSnap s = snapshot(hall);
  TEST_ASSERT_FALSE(should_blank(s, cfg, t0 + 2 * T225 + 400000));
  TEST_ASSERT_TRUE(should_blank(s, cfg, t0 + 2 * T225 + 1500001));    // no pulse for 1.5 s
  // a hand turn: one pulse 3 s later restarts the estimate (not a 2 s period)
  hall_pulse(hall, cfg, t0 + 2 * T225 + 3000000);
  s = snapshot(hall);
  TEST_ASSERT_FALSE(s.valid);
  TEST_ASSERT_EQUAL_UINT32(0, s.rev_us);
  TEST_ASSERT_TRUE(should_blank(s, cfg, t0 + 2 * T225 + 3000100));
  // slow pulses at 45 rpm (1333 ms) never validate
  reset();
  for (int i = 0; i < 6; i++) hall_pulse(hall, cfg, t0 + i * 1333333);
  s = snapshot(hall);
  TEST_ASSERT_FALSE(s.valid);
}

void test_speed_jump_resyncs() {
  reset();
  int64_t t = 1000000;
  hall_pulse(hall, cfg, t); t += T225; hall_pulse(hall, cfg, t); t += T225; hall_pulse(hall, cfg, t);
  TEST_ASSERT_TRUE(snapshot(hall).valid);
  t += 200000; hall_pulse(hall, cfg, t);                 // 25 % faster: not a filter step, a restart
  HallSnap s = snapshot(hall);
  TEST_ASSERT_FALSE(s.valid);
  TEST_ASSERT_EQUAL_UINT32(200000, s.rev_us);
  TEST_ASSERT_EQUAL_UINT32(1, s.resyncs);
  t += 200000; hall_pulse(hall, cfg, t);
  TEST_ASSERT_TRUE(snapshot(hall).valid);
}

// Run the column task's planning loop over three revolutions and check the column sequence and fire times
void test_plan_sequence_at_225_rpm() {
  reset();
  int64_t t0 = 1000000;
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  SchedState st;
  int64_t now = t0 + 2 * T225 + 50;                   // woken by the third pulse
  int64_t next_pulse = t0 + 3 * T225;
  // column 0's edge is the pulse itself, so 50 us after the pulse the earliest reachable column is 1 (a cold start
  // misses column 0 of its first revolution; nothing is counted as skipped). From then on 1, 2, ... 95, 0, 1, ...
  int expect_col = 1, cols = 0, ticks = 0;
  for (int n = 0; n < 96 * 3; n++) {
    if (now >= next_pulse) { hall_pulse(hall, cfg, next_pulse); next_pulse += T225; }
    HallSnap h = snapshot(hall);
    TEST_ASSERT_FALSE(should_blank(h, cfg, now));
    Plan p = plan_next(st, h, cfg, now, SPI_US, BUILD_US);
    TEST_ASSERT_EQUAL_MESSAGE(expect_col, p.col, "column sequence");
    TEST_ASSERT_FALSE_MESSAGE(p.late, "late");
    TEST_ASSERT_EQUAL_MESSAGE(0, p.skipped, "skipped");
    TEST_ASSERT_EQUAL((p.col % 12) == 0, p.tick);
    // the fire time is one SPI frame before the column edge, and at least build_us ahead
    int64_t edge = h.t + (int64_t)p.k * (int64_t)h.rev_us / 96;
    TEST_ASSERT_EQUAL(edge - SPI_US, p.t_fire);
    TEST_ASSERT_TRUE(p.t_fire - now >= BUILD_US);
    TEST_ASSERT_TRUE(p.t_fire - now <= 4000);
    mark_sent(st, p);
    cols++; ticks += p.tick;
    expect_col = (expect_col + 1) % 96;
    int64_t wake = next_wake(p, h, cfg, SPI_US, BUILD_US, SLACK_US);
    TEST_ASSERT_TRUE(wake > p.t_fire);
    now = wake;
  }
  TEST_ASSERT_EQUAL(96 * 3, cols);
  TEST_ASSERT_EQUAL(8 * 3, ticks);
  TEST_ASSERT_EQUAL_UINT32(96 * 3, st.cols_done);
  TEST_ASSERT_EQUAL_UINT32(0, st.late);
  TEST_ASSERT_EQUAL_UINT32(0, st.skipped);
  // column edges are 2,778 us apart: check with the last plan
  TEST_ASSERT_UINT32_WITHIN(2, 2777, (uint32_t)(snapshot(hall).rev_us / 96));
}

// The rotor speeds up 1 % per revolution (a knob turn): re-anchoring keeps the error inside one revolution, no
// duplicate columns, at most one skipped column per revolution, and the estimate stays valid (1 % < 5 %).
void test_speed_drift_is_absorbed_by_reanchoring() {
  reset();
  int64_t t = 1000000;
  int64_t T = T225;
  hall_pulse(hall, cfg, t); t += T; hall_pulse(hall, cfg, t); t += T; hall_pulse(hall, cfg, t);
  SchedState st;
  int64_t now = t + 50;
  int64_t next_pulse = t + T;
  int last_col = -1;
  int dup = 0;
  for (int n = 0; n < 96 * 12; n++) {
    if (now >= next_pulse) {
      hall_pulse(hall, cfg, next_pulse);
      T = T * 99 / 100;
      next_pulse += T;
    }
    HallSnap h = snapshot(hall);
    TEST_ASSERT_TRUE(h.valid);
    Plan p = plan_next(st, h, cfg, now, SPI_US, BUILD_US);
    if (p.col == last_col) dup++;
    TEST_ASSERT_TRUE(p.skipped <= 2);
    last_col = p.col;
    mark_sent(st, p);
    now = std::max(next_wake(p, h, cfg, SPI_US, BUILD_US, SLACK_US), p.t_fire + 1);
  }
  TEST_ASSERT_EQUAL(0, dup);
  TEST_ASSERT_TRUE(st.skipped <= 24);                  // a 1 %/rev speed error is ~1 column per revolution; re-anchoring caps it at that
  TEST_ASSERT_EQUAL_UINT32(0, st.late);
}

void test_late_plan_fires_now_and_early_wake_waits() {
  reset();
  int64_t t0 = 1000000;
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  HallSnap h = snapshot(hall);
  SchedState st;
  // woken 10 us before column 1's edge: its fire time (edge - 704) is past -> column 2 is the earliest reachable
  int64_t edge1 = h.t + (int64_t)h.rev_us / 96;
  Plan p = plan_next(st, h, cfg, edge1 - 10, SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(2, p.col);
  TEST_ASSERT_FALSE(p.late);
  mark_sent(st, p);
  // woken again much too early for column 3: the plan still says column 3, fire later
  Plan p2 = plan_next(st, h, cfg, edge1, SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(3, p2.col);
  TEST_ASSERT_TRUE(p2.t_fire > edge1 + 2000);
  // a plan asked for after column 3's fire time (we never sent it): late, fire immediately, nothing skipped
  int64_t edge3 = h.t + 3 * (int64_t)h.rev_us / 96;
  Plan p3 = plan_next(st, h, cfg, edge3 - SPI_US + 100, SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(4, p3.col);                      // 3 is no longer reachable with build time: it is skipped
  TEST_ASSERT_EQUAL(1, p3.skipped);
  TEST_ASSERT_FALSE(p3.late);
}

void test_reanchor_continues_the_column_count() {
  reset();
  int64_t t0 = 1000000;
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  SchedState st;
  HallSnap h = snapshot(hall);
  // send columns 1..96 (96 = column 0 of the next revolution, predicted) before the pulse arrives; column 0 of this
  // revolution is unreachable 50 us after its own edge
  int64_t now = h.t + 50;
  for (int k = 1; k <= 96; k++) {
    Plan p = plan_next(st, h, cfg, now, SPI_US, BUILD_US);
    TEST_ASSERT_EQUAL(k, p.k);
    mark_sent(st, p);
    now = next_wake(p, h, cfg, SPI_US, BUILD_US, SLACK_US);
  }
  // the pulse arrives exactly on time: the next column is 1, not 0 again
  hall_pulse(hall, cfg, t0 + 3 * T225);
  h = snapshot(hall);
  Plan p = plan_next(st, h, cfg, t0 + 3 * T225 + 30, SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(1, p.col);
  TEST_ASSERT_EQUAL(0, p.skipped);
  // the pulse arrives early (rotor faster than predicted) after only 94 columns were sent: column 0 follows at once
  reset(); st = SchedState();
  hall_pulse(hall, cfg, t0); hall_pulse(hall, cfg, t0 + T225); hall_pulse(hall, cfg, t0 + 2 * T225);
  h = snapshot(hall); now = h.t + 50;
  for (int k = 0; k < 94; k++) { Plan q = plan_next(st, h, cfg, now, SPI_US, BUILD_US); mark_sent(st, q); now = next_wake(q, h, cfg, SPI_US, BUILD_US, SLACK_US); }
  hall_pulse(hall, cfg, t0 + 3 * T225 - 6000);
  h = snapshot(hall);
  Plan q = plan_next(st, h, cfg, t0 + 3 * T225 - 6000 + 20, SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(1, q.col);                        // column 0's fire time was 704 us before the pulse: unreachable
  TEST_ASSERT_EQUAL(1, q.skipped);                    // ... and counted as skipped (columns 94, 95 of the old revolution are not)
  TEST_ASSERT_FALSE(q.late);
  mark_sent(st, q);
  Plan q2 = plan_next(st, h, cfg, next_wake(q, h, cfg, SPI_US, BUILD_US, SLACK_US), SPI_US, BUILD_US);
  TEST_ASSERT_EQUAL(2, q2.col);
  TEST_ASSERT_EQUAL(0, q2.skipped);
}

void test_image_col_direction_and_offset() {
  TEST_ASSERT_EQUAL(5, image_col(5, 1, 0));
  TEST_ASSERT_EQUAL(6, image_col(5, 1, 8));
  TEST_ASSERT_EQUAL(4, image_col(5, 1, -8));
  TEST_ASSERT_EQUAL(5, image_col(5, 1, 7));          // 7/8 of a column rounds down
  TEST_ASSERT_EQUAL(95, image_col(0, 1, -1));        // floor(-1/8) = -1
  TEST_ASSERT_EQUAL(95, image_col(1, -1, 0));
  TEST_ASSERT_EQUAL(0, image_col(0, -1, 0));
  TEST_ASSERT_EQUAL(1, image_col(95, -1, 0));
  for (int c = 0; c < 96; c++) for (int o = -800; o <= 800; o += 37) { int v = image_col(c, 1, o); TEST_ASSERT_TRUE(v >= 0 && v < 96); }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_config_defaults);
  RUN_TEST(test_first_pulse_only_anchors_and_two_agreeing_periods_validate);
  RUN_TEST(test_bounce_is_rejected_and_changes_nothing);
  RUN_TEST(test_blank_when_stopped_or_too_slow);
  RUN_TEST(test_speed_jump_resyncs);
  RUN_TEST(test_plan_sequence_at_225_rpm);
  RUN_TEST(test_speed_drift_is_absorbed_by_reanchoring);
  RUN_TEST(test_late_plan_fires_now_and_early_wake_waits);
  RUN_TEST(test_reanchor_continues_the_column_count);
  RUN_TEST(test_image_col_direction_and_offset);
  return UNITY_END();
}
