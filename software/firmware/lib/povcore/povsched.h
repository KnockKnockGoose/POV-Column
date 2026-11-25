// povsched.h - hall-pulse period estimate and the column scheduler of the POV LED Column v2. Pure logic, no hardware:
// the hall ISR feeds hall_pulse(), the column task calls snapshot()/should_blank()/plan_next(), and the host tests
// drive the same functions with synthetic pulse times.
//
// Design (software report 1.3, QA review B1c): the pulse re-anchors the schedule every revolution, so a prediction error
// never accumulates past one revolution. The period is a first-order filter (alpha 1/4) that is trusted only after two
// consecutive periods agree within 5 %; the first pulse after boot (or after a stop) only sets the anchor. Pulses
// closer than a quarter of the fastest plausible revolution are bounce and are rejected.
#pragma once
#include "pov_compat.h"
#include "povmap.h"

namespace pov {

struct SchedCfg {
  uint32_t cols = POV_COLS;
  uint32_t col_us_min = 900;         // faster than this per column (>= 694 rpm) is implausible
  uint32_t lockout_us = 900 * POV_COLS / 4;   // 21.6 ms: a pulse closer than a quarter revolution is a bounce
  uint32_t rev_us_max = 1200000;     // slower than 50 rpm: blank (bench 2026-11-20: was 600000 / 100 rpm; lets a slow, flickery picture show)
  uint32_t no_pulse_us = 1500000;    // no pulse for 1.5 s -> LEDs off (must exceed rev_us_max, else it blanks mid-turn below 120 rpm)
  uint32_t agree_pct = 15;           // two consecutive periods within this -> the estimate is trusted (bench 2026-11-20: was 5; the drive stick-slips)
};

// Written by the hall ISR, read by the column task. `seq` is a seqlock: odd while an update is in progress.
struct Hall {
  volatile uint32_t seq = 0;
  volatile int64_t t = 0, t_prev = 0;   // the last two accepted pulses, esp_timer_get_time() us (0 = none yet)
  volatile uint32_t rev_us = 0;         // filtered period, 0 = unknown
  volatile uint32_t pulses = 0, rejected = 0, resyncs = 0;
  volatile uint8_t agree = 0;           // consecutive periods within agree_pct of the estimate
  volatile bool valid = false;          // two periods agreed: the schedule may run
};

struct HallSnap {
  int64_t t, t_prev;
  uint32_t rev_us, pulses, rejected, resyncs;
  uint8_t agree;
  bool valid;
};

// ISR path (keep it integer-only and short). Returns true if the pulse was accepted.
static inline bool IRAM_ATTR hall_pulse(Hall& h, const SchedCfg& c, int64_t now) {
  if (h.t != 0) {
    int64_t dt = now - h.t;
    if (dt < (int64_t)c.lockout_us) { h.rejected = h.rejected + 1; return false; }   // (x = x + 1: C++20 deprecates ++ on volatile)
  }
  h.seq = h.seq + 1;                                  // odd: update in progress
  if (h.t == 0) {                                     // first pulse ever: anchor only, no period yet
    h.t = now;
    h.pulses = h.pulses + 1;
  } else {
    int64_t dt = now - h.t;
    h.t_prev = h.t;
    h.t = now;
    h.pulses = h.pulses + 1;
    if (dt > (int64_t)c.rev_us_max) {                 // stopped, or turned by hand: restart the estimate
      h.rev_us = 0; h.agree = 0; h.valid = false;
    } else {
      uint32_t d = (uint32_t)dt;
      if (h.rev_us == 0) {
        h.rev_us = d; h.agree = 1; h.valid = false;
      } else {
        uint32_t ref = h.rev_us;
        uint32_t diff = d > ref ? d - ref : ref - d;
        if (diff * 100u <= ref * c.agree_pct) {
          if (h.agree < 255) h.agree = (uint8_t)(h.agree + 1);
          h.rev_us = (uint32_t)((int32_t)ref + ((int32_t)d - (int32_t)ref) / 4);   // IIR, alpha 1/4
          h.valid = h.agree >= 2;
        } else {                                      // speed jumped: start over from this period
          h.rev_us = d; h.agree = 1; h.valid = false; h.resyncs = h.resyncs + 1;
        }
      }
    }
  }
  h.seq = h.seq + 1;                                  // even: consistent
  return true;
}

// Consistent copy of the ISR's state (retries if an update was in progress)
static inline HallSnap snapshot(const Hall& h) {
  HallSnap s;
  for (;;) {
    uint32_t s0 = h.seq;
    s.t = h.t; s.t_prev = h.t_prev; s.rev_us = h.rev_us; s.pulses = h.pulses; s.rejected = h.rejected;
    s.resyncs = h.resyncs; s.agree = h.agree; s.valid = h.valid;
    if ((s0 & 1u) == 0 && h.seq == s0) return s;
  }
}

static inline bool should_blank(const HallSnap& h, const SchedCfg& c, int64_t now) {
  return !h.valid || h.rev_us == 0 || h.rev_us > c.rev_us_max || h.t == 0 || (now - h.t) > (int64_t)c.no_pulse_us;
}

// What the column task does next
struct Plan {
  int64_t t_fire;   // start the SPI transfer at this time: the LEDs latch one frame time later, on the column edge
  int32_t k;        // column index since the anchor (may exceed cols-1 while the next pulse is still to come)
  int col;          // k mod cols: the scheduler column strip 0 shows
  bool tick;        // this column starts a refresh tick (every cols/8 columns): swap frames here
  bool late;        // the fire time had already passed when planned (fire immediately)
  int32_t skipped;  // columns that could not be reached in time and were dropped
};

struct SchedState {
  int64_t anchor = 0;   // the hall time the column indices are counted from
  int32_t last_k = -1;  // last column index sent (relative to anchor)
  uint32_t cols_done = 0, late = 0, skipped = 0;
};

// Decide the next column at time `now`: the earliest column edge whose fire time (edge - spi_us) is still at least
// build_us ahead, never re-sending a column. A new pulse re-anchors: index k of the old revolution is k - cols now.
static inline Plan plan_next(SchedState& s, const HallSnap& h, const SchedCfg& c, int64_t now, uint32_t spi_us,
                             uint32_t build_us) {
  Plan p;
  bool cold = s.anchor == 0;              // first plan since boot / since a blank: nothing was missed before it
  if (s.anchor != h.t) {
    if (!cold) s.last_k -= (int32_t)c.cols;
    if (s.last_k < -1) s.last_k = -1;
    s.anchor = h.t;
  }
  int64_t T = h.rev_us;
  int64_t need = (now - h.t) + spi_us + build_us;
  int32_t k = need <= 0 ? 0 : (int32_t)((need * (int64_t)c.cols + T - 1) / T);   // ceil
  if (k < 0) k = 0;
  p.skipped = 0;
  if (k <= s.last_k) k = s.last_k + 1;
  else if (!cold) p.skipped = k - (s.last_k + 1);
  int64_t edge = h.t + ((int64_t)k * T) / (int64_t)c.cols;
  p.t_fire = edge - spi_us;
  p.late = p.t_fire < now;
  if (p.late) p.t_fire = now;
  p.k = k;
  p.col = (int)(k % (int32_t)c.cols);
  if (p.col < 0) p.col += (int)c.cols;
  p.tick = (p.col % (int)(c.cols / POV_K_PASSES)) == 0;
  return p;
}

static inline void mark_sent(SchedState& s, const Plan& p) {
  s.last_k = p.k;
  s.cols_done++;
  if (p.late) s.late++;
  s.skipped += (uint32_t)p.skipped;
}

// When to wake for the column after `p`: its fire time minus the build time and the busy-wait slack
static inline int64_t next_wake(const Plan& p, const HallSnap& h, const SchedCfg& c, uint32_t spi_us, uint32_t build_us,
                                uint32_t slack_us) {
  int64_t edge = h.t + ((int64_t)(p.k + 1) * (int64_t)h.rev_us) / (int64_t)c.cols;
  return edge - spi_us - build_us - slack_us;
}

// Image column for scheduler column `col`: direction and the angular offset trim (1/8-column steps)
static inline int image_col(int col, int dir, int offset_x8) {
  int off = offset_x8 >= 0 ? offset_x8 / 8 : -((-offset_x8 + 7) / 8);
  int c = (dir < 0 ? -col : col) + off;
  c %= POV_COLS;
  if (c < 0) c += POV_COLS;
  return c;
}

}  // namespace pov
