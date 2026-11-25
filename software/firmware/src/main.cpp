// =====================================================================================================================
//  POV LED Column v2 - column firmware. First compiled 2026-11-03 (docs/2026-11-03-firmware-build.md).
//  Architecture: docs/2026-11-02-software-and-ai-content.md section 1. The pure logic lives in lib/povcore and is
//  host-tested (test/); this file is the glue to the ESP32: SPI DMA, the hall interrupt, the GPTimer, FreeRTOS tasks,
//  LittleFS, Wi-Fi, the web API, OTA.
//  0.4 (2026-11-14, Wi-Fi control review, docs/2026-11-14-wifi-control-review.md): animations load into a fixed 64 KB
//  arena owned by the player task (no heap fragmentation: any stored file plays at any time), uploads are checked as
//  they stream in (no 64 KB malloc, no crash on a reject), crash recorder (/api/crash), OTA pause (/api/ota-prep and
//  automatic on every OTA start), remote reboot (/api/reboot), persistent simulated hall, link/CPU diagnostics.
//
//  core 1 (real time)                         core 0 (everything else)
//  ------------------                         ------------------------
//  hall ISR  -> povsched::hall_pulse          Wi-Fi (STA, AP fallback) + mDNS pov.local
//  GPTimer alarm -> column task (prio 23)     ESPAsyncWebServer: /api/*, /ws, /update, static UI (async_tcp, prio 10)
//    plan_next: which column edge is next     player task (prio 3): loads .pova into the arena, frames on refresh ticks
//    build 2 x 704 B SK9822 frames            render task: captions (captions.h), text scroller, acks
//    spi_device_queue_trans x2 (DMA)          probe task (prio 1): scheduling lag of core 0 (diagnostics)
//    swap frames at refresh-tick boundaries   simulated hall: esp_timer callback (prio 22) when sim_rpm > 0
//  loop() (prio 1): ArduinoOTA, OTA guard,    power cap: per-animation scale of the 5-bit field
//    timers, sim yield, WS cleanup            settings in NVS (Preferences)
//
//  Hardware (electrical report rev e, 30-pin DOIT DevKit V1): chain 0 on VSPI (SPI3) MOSI 23 / SCK 18, chain 1 on HSPI
//  (SPI2) MOSI 13 / SCK 14, both through the 74AHCT125; hall A3144 on GPIO 26 (10 k pull-up to 3V3, falls once per
//  revolution). 8 MHz SPI: 704 B = 0.704 ms per chain against a 2.78 ms column at 225 rpm.
// =====================================================================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <LittleFS.h>
#include <ArduinoOTA.h>
#include <Update.h>
#include "pov_ota.h"          // OTA hardening: rollback guard, receive timeout, build id (docs/2026-11-13-ota-failure-review.md)
#include "pov_crash.h"        // crash recorder: /api/crash (docs/2026-11-14-wifi-control-review.md)
#include <Preferences.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <driver/spi_master.h>
#include <driver/gptimer.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>

#include "povframe.h"
#include "povsched.h"
#include "pova.h"
#include "captions.h"
#include "povpattern.h"

#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"    // gitignored: WIFI_SSID, WIFI_PASS, OTA_PASS, POV_TOKEN
#else
#define WIFI_SSID "FILL_IN"
#define WIFI_PASS "FILL_IN"
#define OTA_PASS "FILL_IN"
#define POV_TOKEN ""
#endif
#ifndef POV_FW_VERSION
#define POV_FW_VERSION "0.2-dev"
#endif

// ---------------------------------------------------------------- hardware constants (v2 report, electrical rev e)
static const int PIN_HALL = 26;                   // moved from IO27 (damaged 2026-11-12); A3144, open collector, 10 k pull-up to 3V3, falls once per rev
static const int PIN_D0 = 23, PIN_C0 = 18;        // chain 0: VSPI = SPI3 MOSI / SCK (IO_MUX pins) via 74AHCT125
static const int PIN_D1 = 13, PIN_C1 = 14;        // chain 1: HSPI = SPI2 MOSI / SCK
static const int SPI_HZ = 8000000;
static const uint32_t SPI_US = (uint32_t)((uint64_t)POV_FRAME_BYTES * 8 * 1000000ULL / SPI_HZ);   // 704 us per chain
RTC_NOINIT_ATTR static uint32_t boot_count;           // survives resets (not power-off): counts a reboot loop
static int reset_reason = 0;
static const uint32_t BUILD_US = 60;             // time to build both chains' frames (measured: build_us_max on /api/status)
static const uint32_t SLACK_US = 100;             // wake this much before the fire time and busy-wait the rest
static const uint32_t CAP_MA = pov::CAP_MA;       // 2,600 mA for LEDs incl. dark current (the ESP32's 120 mA is on top)
static const uint32_t BOOT_TEXT_MS = 10000;       // scroll the IP for 10 s after boot
static const uint32_t OTA_PREP_DEFAULT_S = 180;   // /api/ota-prep pauses the display this long unless an OTA starts

// ---------------------------------------------------------------- settings (NVS)
struct Settings {
  uint8_t gb = 31;            // requested 5-bit current field (the cap may lower it per animation)
  int8_t dir = +1;            // +1 / -1: un-mirrors the picture if the motor turns the other way
  int16_t offset_x8 = 0;      // angular trim in 1/8-column steps
  bool autoplay = true;
  char last[32] = "";
  bool front_only = false;    // paint only the 180 deg facing front_deg (per strip, from the hall angle)
  int16_t front_deg = 0;
  uint16_t sim_rpm = 0;       // saved simulated hall (0 = none): starts at boot, yields to real hall pulses
  uint8_t tx_qdbm = 52;       // Wi-Fi TX power after the join, 0.25 dBm units (52 = 13 dBm, the bank-power default)
} settings;
static Preferences prefs;

static void settings_load() {
  prefs.begin("pov", true);
  settings.gb = prefs.getUChar("gb", 31);
  settings.dir = prefs.getChar("dir", 1) < 0 ? -1 : 1;
  settings.offset_x8 = prefs.getShort("offx8", 0);
  settings.autoplay = prefs.getBool("autoplay", true);
  settings.front_only = prefs.getBool("fronton", false);
  settings.front_deg = prefs.getShort("frontdeg", 0);
  settings.sim_rpm = prefs.getUShort("simrpm", 0);
  settings.tx_qdbm = prefs.getUChar("txq", 52);
  String last = prefs.getString("last", "");
  pov::strlcpy_(settings.last, last.c_str(), sizeof settings.last);
  prefs.end();
  if (settings.gb < 1 || settings.gb > 31) settings.gb = 31;
  if (settings.sim_rpm > 1200) settings.sim_rpm = 0;
  settings.tx_qdbm = pov::clampv<uint8_t>(settings.tx_qdbm, 8, 78);
}

static void settings_save() {
  prefs.begin("pov", false);
  prefs.putUChar("gb", settings.gb);
  prefs.putChar("dir", settings.dir);
  prefs.putShort("offx8", settings.offset_x8);
  prefs.putBool("autoplay", settings.autoplay);
  prefs.putBool("fronton", settings.front_only);
  prefs.putShort("frontdeg", settings.front_deg);
  prefs.putUShort("simrpm", settings.sim_rpm);
  prefs.putUChar("txq", settings.tx_qdbm);
  prefs.putString("last", settings.last);
  prefs.end();
}

// ---------------------------------------------------------------- shared state
enum PlayMode : uint8_t { MODE_OFF, MODE_ANIM, MODE_CAPTIONS, MODE_LIVE, MODE_PATTERN, MODE_TEXT };
static const char* const MODE_NAMES[] = {"off", "anim", "captions", "live", "pattern", "text"};
static volatile PlayMode play_mode = MODE_OFF;

static DMA_ATTR uint8_t spi_buf[2][2][POV_FRAME_BYTES];      // [chain][ping-pong]
static DMA_ATTR uint8_t blank_buf[2][POV_FRAME_BYTES];
static spi_device_handle_t spi_dev[2];
static spi_transaction_t spi_tr[2][2], blank_tr[2];           // one descriptor per buffer: never reused while in flight
static volatile uint32_t spi_fail = 0;

static uint8_t frame_buf[2][POV_FRAME_PIXELS];                // decoded palette-index frames, double buffered
static volatile uint8_t frame_show = 0;                       // index of the frame the column engine reads
static volatile bool frame_ready = false;                     // frame_buf[!frame_show] holds the next frame
static portMUX_TYPE frame_mux = portMUX_INITIALIZER_UNLOCKED; // guards frame_show / frame_ready / the spare buffer
static pov::PalBytes pal_set[2];                               // double-buffered LED palette (core 0 writes, core 1 reads)
static volatile uint8_t pal_show = 0;
static volatile bool pal_with_frame = false;                  // the spare palette goes live with the next frame swap
static portMUX_TYPE pal_mux = portMUX_INITIALIZER_UNLOCKED;   // palette writers (several core-0 tasks)
static uint8_t cur_gb = 31;                                   // current field in use after the cap
static uint8_t last_rgb[POV_MAX_PAL][3]; static int last_npal = 1; static uint8_t last_gb_req = 0;   // re-publish (test_dark)

// Animation: the file image lives in a 64 KB arena allocated once at boot (review 2026-11-14: load_anim used to malloc
// the new file while the old one was still allocated; on the fragmented ~100 KB heap a 62 KB file could not be played).
// Only the player task reads or writes `anim` and the arena; other tasks ask it to load (request_load).
static PovaAnim anim;
static uint8_t* arena = nullptr;
static uint32_t anim_worst_ma31 = 0;                          // worst rotor position of the loaded animation at gb 31
static volatile uint32_t anim_gen = 0;                        // bumped by each load: the player restarts at frame 0
enum LoadState : uint8_t { LOAD_IDLE, LOAD_QUEUED, LOAD_BUSY, LOAD_OK, LOAD_ERR };
static const char* const LOAD_NAMES[] = {"idle", "queued", "loading", "ok", "error"};
static portMUX_TYPE req_mux = portMUX_INITIALIZER_UNLOCKED;
static char req_name[32] = "";
static volatile bool req_pending = false, refit_pending = false;
static volatile LoadState load_state = LOAD_IDLE;
static char load_name[32] = "", load_err[72] = "";
static volatile uint32_t load_ms = 0, loads_ok = 0, loads_failed = 0;

static pov::Hall hall;
static pov::Hall real_hall;                                    // the real sensor while the simulator drives `hall`
static pov::SchedCfg sched_cfg;
static TaskHandle_t col_task = nullptr, render_task_h = nullptr, player_h = nullptr, probe_h = nullptr;
static gptimer_handle_t col_timer = nullptr;
static volatile bool running = false, ota_active = false;
static volatile uint32_t tick_count = 0;                      // refresh ticks since boot
static volatile uint32_t cols_drawn = 0, late_cols = 0, skipped_cols = 0, build_us_max = 0;
static volatile bool tick_swapped = false;
static volatile int64_t tick_swap_us = 0;
static const uint32_t NOTIFY_TICK = 1, NOTIFY_MSG = 2;

// OTA pause: LEDs dark, simulator off, player idle, live sockets closed, full TX power (review 2026-11-14)
static volatile bool paused = false;
static volatile uint32_t pause_until_ms = 0;                  // auto-resume (0 = until reboot or an explicit resume)
static volatile uint32_t sim_before_pause = 0;

// diagnostics (review 2026-11-14): tell CPU starvation from a radio / power problem
static volatile bool test_dark = false;                       // engine + SPI run, every LED at current field 0
static volatile bool test_nospi = false;                      // engine runs, no SPI transfers (LEDs blanked once)
static volatile uint32_t live_frames = 0, live_bad = 0;
static volatile uint32_t col_busy_us = 0;                     // column task busy time (accumulated)
static volatile uint32_t col_busy_pct_x10 = 0;
static volatile uint32_t lag0_win_us = 0, lag0_max_us = 0;    // core 0: probe task wake-up lateness (5 s window / ever)
static volatile uint32_t lag1_win_us = 0, lag1_max_us = 0;    // core 1: loop() iteration gap beyond its 5 ms delay
static volatile uint32_t wifi_disc = 0; static volatile uint8_t wifi_last_reason = 0;
static volatile uint32_t api_reqs = 0;
static uint32_t fs_free = 0;                                  // cached: LittleFS.usedBytes() walks the whole filesystem
static void update_fs_free() { fs_free = (uint32_t)(LittleFS.totalBytes() - LittleFS.usedBytes()); }
static TaskHandle_t loop_h = nullptr, async_h = nullptr;

static AsyncWebServer server(80);
static AsyncWebSocket ws("/ws");
static cap::Captions captions;
static pat::Scroller scroller;
static uint32_t text_until_ms = 0;                            // text mode ends here (0 = no end)
static volatile uint32_t reboot_at_ms = 0;
static volatile bool http_ota_ok = false;                    // the /update upload so far is good
static uint8_t stage_buf[POV_FRAME_PIXELS];
static uint8_t tmp_frame[POV_FRAME_PIXELS];                   // player task only
static uint32_t staged_ids[8]; static uint8_t n_staged = 0;
static uint16_t live_duty[POV_MAX_PAL]; static pov::PalRgb live_rgb; static int live_npal = 0; static uint8_t live_gb = 0;

// ---------------------------------------------------------------- frames and palettes (core 0 side)
static void stage_frame(const uint8_t* src) {
  portENTER_CRITICAL(&frame_mux);
  memcpy(frame_buf[frame_show ^ 1], src, POV_FRAME_PIXELS);  // ~4 KB, a few microseconds
  frame_ready = true;
  portEXIT_CRITICAL(&frame_mux);
}

// Gamma + current field into the spare palette set, then flip (the column task reads whole sets). with_frame = the new
// palette goes live together with the next staged frame (no old-frame-in-new-colours flash when an animation changes).
static void publish_palette(const uint8_t (*rgb)[3], int npal, uint8_t gb, bool with_frame = false) {
  npal = pov::clampv(npal, 1, (int)POV_MAX_PAL);
  portENTER_CRITICAL(&pal_mux);
  if (rgb != last_rgb) memcpy(last_rgb, rgb, 3u * npal);
  last_npal = npal; last_gb_req = gb;
  uint8_t spare = pal_show ^ 1;
  pov::make_palette(pal_set[spare], rgb, npal, test_dark ? 0 : gb);
  if (with_frame) pal_with_frame = true;
  else { pal_with_frame = false; pal_show = spare; }
  cur_gb = gb;
  portEXIT_CRITICAL(&pal_mux);
}

// Per-frame cap: the largest field <= settings.gb that keeps the worst rotor position of `frame` under CAP_MA
static uint8_t capped_gb(const uint8_t* frame, const uint16_t duty[POV_MAX_PAL]) {
  return pov::fit_gb(pov::worst_column_ma(frame, duty, 31), settings.gb, CAP_MA);
}

static void show_pattern_frame(const uint8_t* frame, uint8_t (*rgb)[3], int npal) {
  uint16_t duty[POV_MAX_PAL];
  pov::palette_duty(rgb, npal, duty);
  publish_palette(rgb, npal, capped_gb(frame, duty));
  stage_frame(frame);
}

// ---------------------------------------------------------------- SPI (two hosts, DMA, no result queue)
// IDF 5.5 (arduino-esp32 3.3.x) rejects SPI_DEVICE_NO_RETURN_RESULT without a post callback (ESP_ERR_INVALID_ARG ->
// boot loop, found 2026-11-13); an empty one keeps the no-result-queue behaviour.
static void IRAM_ATTR spi_post_cb(spi_transaction_t*) {}

static void setup_spi(spi_host_device_t host, int mosi, int sck, spi_device_handle_t* dev) {
  spi_bus_config_t bus = {};
  bus.mosi_io_num = mosi; bus.miso_io_num = -1; bus.sclk_io_num = sck;
  bus.quadwp_io_num = -1; bus.quadhd_io_num = -1; bus.max_transfer_sz = POV_FRAME_BYTES;
  ESP_ERROR_CHECK(spi_bus_initialize(host, &bus, SPI_DMA_CH_AUTO));
  spi_device_interface_config_t cfg = {};
  cfg.clock_speed_hz = SPI_HZ; cfg.mode = 0; cfg.spics_io_num = -1; cfg.queue_size = 2;
  cfg.flags = SPI_DEVICE_NO_RETURN_RESULT;        // QA B1b: nothing to reap; one descriptor per buffer instead
  cfg.post_cb = spi_post_cb;                      // required with NO_RETURN_RESULT since IDF 5.5
  ESP_ERROR_CHECK(spi_bus_add_device(host, &cfg, dev));
}

static void queue_frame(int ch, spi_transaction_t& tr, const uint8_t* buf) {
  tr = spi_transaction_t();
  tr.length = POV_FRAME_BYTES * 8;
  tr.tx_buffer = buf;
  if (spi_device_queue_trans(spi_dev[ch], &tr, 0) != ESP_OK) spi_fail = spi_fail + 1;
}

static void blank_all() {
  for (int ch = 0; ch < 2; ch++) queue_frame(ch, blank_tr[ch], blank_buf[ch]);
}

// ---------------------------------------------------------------- hall sensor (core 1 ISR) and the column timer
static esp_timer_handle_t sim_timer = nullptr;
static volatile uint32_t sim_rpm = 0;                          // running simulator rpm (0 = off)
static volatile uint32_t sim_resume_rpm = 0;                   // the simulator stepped aside for real pulses at this rpm

static portMUX_TYPE hall_mux = portMUX_INITIALIZER_UNLOCKED;   // the two writers of `hall` (ISR core 1, sim core 0)

static void IRAM_ATTR hall_isr() {
  int64_t now = esp_timer_get_time();
  if (sim_rpm) { pov::hall_pulse(real_hall, sched_cfg, now); return; }   // simulator owns the schedule: only watch
  portENTER_CRITICAL_ISR(&hall_mux);
  bool ok = pov::hall_pulse(hall, sched_cfg, now);
  portEXIT_CRITICAL_ISR(&hall_mux);
  if (ok) {
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(col_task, &woken);                  // re-anchor the column schedule now
    if (woken) portYIELD_FROM_ISR();
  }
}

// Simulated hall (Brian 2026-11-13, hall not triggering after reassembly): a periodic esp_timer feeds the same pulse
// path as the real sensor at a set rpm, so the image shows and the motor can be tuned until it stands still.
// POST /api/settings {"sim_rpm": N, "sim_persist": true} keeps it across reboots (review 2026-11-14). While it runs the
// hall ISR only feeds `real_hall`; when that sees a steady real rotation the simulator steps aside (sim_yield in loop).
static void sim_cb(void*) {
  portENTER_CRITICAL(&hall_mux);
  bool ok = pov::hall_pulse(hall, sched_cfg, esp_timer_get_time());
  portEXIT_CRITICAL(&hall_mux);
  if (ok) xTaskNotifyGive(col_task);
}
static void set_sim_rpm(uint32_t rpm) {
  if (!sim_timer) { esp_timer_create_args_t a = {}; a.callback = sim_cb; a.name = "simhall"; esp_timer_create(&a, &sim_timer); }
  esp_timer_stop(sim_timer);
  sim_rpm = rpm;
  if (rpm) esp_timer_start_periodic(sim_timer, 60000000ULL / rpm);
}

static bool IRAM_ATTR on_col_alarm(gptimer_handle_t, const gptimer_alarm_event_data_t*, void*) {
  BaseType_t woken = pdFALSE;
  vTaskNotifyGiveFromISR(col_task, &woken);
  return woken == pdTRUE;
}

static void arm_timer(int64_t delay_us) {
  if (delay_us < 20) delay_us = 20;
  uint64_t now = 0;
  gptimer_get_raw_count(col_timer, &now);
  gptimer_alarm_config_t al = {};
  al.alarm_count = now + (uint64_t)delay_us;
  al.reload_count = 0;
  al.flags.auto_reload_on_alarm = false;
  gptimer_set_alarm_action(col_timer, &al);
}

// The column task, pinned to core 1 at a high priority. Each wake-up it asks the scheduler which column edge is next,
// builds both chains' frames into the free ping-pong buffers, busy-waits the last <= 100 us and queues the two DMA
// transfers so the LEDs latch on the column edge; then it arms the one-shot alarm for the next column.
// Measured load (review 2026-11-14): ~0.2 ms per column = ~5 % of core 1 at 150 rpm, ~8 % at 225 rpm (col_busy_pct).
static void column_task(void*) {
  // the timer is created here so its interrupt is allocated on core 1 (esp_intr_alloc binds to the calling core)
  gptimer_config_t tc = {};
  tc.clk_src = GPTIMER_CLK_SRC_DEFAULT; tc.direction = GPTIMER_COUNT_UP; tc.resolution_hz = 1000000;
  ESP_ERROR_CHECK(gptimer_new_timer(&tc, &col_timer));
  gptimer_event_callbacks_t cbs = {};
  cbs.on_alarm = on_col_alarm;
  ESP_ERROR_CHECK(gptimer_register_event_callbacks(col_timer, &cbs, nullptr));
  ESP_ERROR_CHECK(gptimer_enable(col_timer));
  ESP_ERROR_CHECK(gptimer_start(col_timer));
  pinMode(PIN_HALL, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_HALL), hall_isr, FALLING);   // the GPIO ISR lands on this core too

  pov::SchedState st;
  int pp = 0;
  bool spi_was_off = false;
  for (;;) {
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100));
    int64_t now = esp_timer_get_time();
    pov::HallSnap h = pov::snapshot(hall);
    if (ota_active || paused || play_mode == MODE_OFF || pov::should_blank(h, sched_cfg, now)) {
      if (running) { running = false; blank_all(); }
      st = pov::SchedState();
      col_busy_us = col_busy_us + (uint32_t)(esp_timer_get_time() - now);
      continue;
    }
    running = true;
    pov::Plan p = pov::plan_next(st, h, sched_cfg, now, SPI_US, BUILD_US);
    if (p.t_fire - now > (int64_t)(BUILD_US + SLACK_US + 50)) {   // woken early (a pulse): sleep until the right moment
      arm_timer(p.t_fire - now - BUILD_US - SLACK_US);
      col_busy_us = col_busy_us + (uint32_t)(esp_timer_get_time() - now);
      continue;
    }
    if (p.tick) {                                   // refresh tick boundary: all 24 strips change together
      portENTER_CRITICAL(&frame_mux);
      if (frame_ready) {
        frame_show ^= 1; frame_ready = false; tick_swapped = true; tick_swap_us = now;
        if (pal_with_frame) { pal_show ^= 1; pal_with_frame = false; }   // the new animation's colours, same instant
      }
      portEXIT_CRITICAL(&frame_mux);
      tick_count = tick_count + 1;
      if (render_task_h && (play_mode == MODE_CAPTIONS || play_mode == MODE_TEXT)) xTaskNotify(render_task_h, NOTIFY_TICK, eSetBits);
    }
    int img_col = pov::image_col(p.col, settings.dir, settings.offset_x8);
    uint32_t mask = settings.front_only ? pov::front_mask(p.col, settings.front_deg) : 0xFFFFFFu;
    const uint8_t* f = frame_buf[frame_show];
    const uint8_t (*pal)[4] = pal_set[pal_show];
    int64_t b0 = esp_timer_get_time();
    for (int ch = 0; ch < 2; ch++) pov::build_column(spi_buf[ch][pp], ch, f, img_col, pal, mask);
    uint32_t bu = (uint32_t)(esp_timer_get_time() - b0);
    if (bu > build_us_max) build_us_max = bu;
    while (esp_timer_get_time() < p.t_fire) { }      // short busy wait: the alarm gave us ~100 us of slack
    if (test_nospi) {                                // diagnostics: everything but the SPI transfers
      if (!spi_was_off) { blank_all(); spi_was_off = true; }
    } else {
      spi_was_off = false;
      for (int ch = 0; ch < 2; ch++) queue_frame(ch, spi_tr[ch][pp], spi_buf[ch][pp]);
    }
    pp ^= 1;
    pov::mark_sent(st, p);
    cols_drawn = cols_drawn + 1;
    late_cols = st.late; skipped_cols = st.skipped;
    int64_t wake = pov::next_wake(p, h, sched_cfg, SPI_US, BUILD_US, SLACK_US);
    int64_t t_end = esp_timer_get_time();
    col_busy_us = col_busy_us + (uint32_t)(t_end - now);
    arm_timer(wake - t_end);
  }
}

// ---------------------------------------------------------------- animation playback (core 0, player task)
static bool valid_name(const char* name) {
  size_t n = name ? strlen(name) : 0;
  if (n == 0 || n > 28) return false;
  for (size_t i = 0; i < n; i++) {
    char c = name[i];
    if (!(isalnum((unsigned char)c) || c == '_' || c == '-' || c == '.')) return false;
  }
  return name[0] != '.';
}

// Any task: ask the player to load and play /anims/<name>.pova. Returns at once; /api/status "load" shows the outcome.
static void request_load(const char* name) {
  portENTER_CRITICAL(&req_mux);
  pov::strlcpy_(req_name, name, sizeof req_name);
  req_pending = true;
  portEXIT_CRITICAL(&req_mux);
  pov::strlcpy_(load_name, name, sizeof load_name);
  load_err[0] = 0;
  load_state = LOAD_QUEUED;
  if (player_h) xTaskNotifyGive(player_h);
}

static void cancel_load() { req_pending = false; if (load_state == LOAD_QUEUED) load_state = LOAD_IDLE; }

static void load_fail(const char* name, const char* why) {
  snprintf(load_err, sizeof load_err, "%s: %s", name, why);
  load_state = LOAD_ERR;
  loads_failed = loads_failed + 1;
  Serial.printf("load %s failed: %s\n", name, why);
}

// Player task only. The arena is overwritten in place: nothing else reads it, and the column task keeps showing the
// last staged frame (frame_buf, a separate buffer) with its palette until frame 0 of the new animation is swapped in at
// a tick boundary together with the new palette. Measured target: < 2 s from the request to the new picture.
static void do_load(const char* name) {
  POV_OP(OP_LOAD);
  uint32_t t0 = millis();
  load_state = LOAD_BUSY;
  if (!arena) { load_fail(name, "no animation memory (arena allocation failed at boot)"); return; }
  String path = String("/anims/") + name + ".pova";
  File f = LittleFS.open(path, "r");
  if (!f) { load_fail(name, "not found"); return; }
  size_t n = f.size();
  if (n < 24 || n > POVA_MAX_FILE) { f.close(); load_fail(name, "bad size"); return; }
  bool was_anim = play_mode == MODE_ANIM;
  anim.file = nullptr;                                          // from here the old animation is gone
  size_t got = f.read(arena, n);
  f.close();
  if (got != n || !pova_parse(anim, arena, n, true) || anim.nframes == 0) {
    anim.file = nullptr;
    if (was_anim) play_mode = MODE_OFF;
    load_fail(name, got != n ? "short read" : "damaged file (CRC or structure)");
    return;
  }
  // per-animation cap: the worst frame's worst rotor position stays under CAP_MA (folded into the 5-bit field); also
  // refuse palette indices >= npal (files stored before 0.4 were not checked for that)
  uint16_t duty[POV_MAX_PAL];
  pov::palette_duty(anim.pal_rgb, anim.npal, duty);
  uint32_t worst = 0;
  for (uint16_t i = 0; i < anim.nframes; i++) {
    bool ok = pova_decode(anim, i, tmp_frame);
    for (int p = 0; ok && p < POV_FRAME_PIXELS; p++) ok = tmp_frame[p] < anim.npal;
    if (!ok) { anim.file = nullptr; if (was_anim) play_mode = MODE_OFF; load_fail(name, "bad frame data"); return; }
    worst = std::max(worst, pov::worst_column_ma(tmp_frame, duty, 31));
    if ((i & 15) == 15) vTaskDelay(1);                          // ~2 ms per frame: let IDLE0 run (task watchdog)
  }
  anim_worst_ma31 = worst;
  anim_gen = anim_gen + 1;
  pova_decode(anim, 0, tmp_frame);
  publish_palette(anim.pal_rgb, anim.npal, pov::fit_gb(worst, settings.gb, CAP_MA), true);
  stage_frame(tmp_frame);
  play_mode = MODE_ANIM;
  load_ms = millis() - t0;
  load_state = LOAD_OK;
  loads_ok = loads_ok + 1;
  Serial.printf("load %s: %u B, %u frames, %u ms\n", name, (unsigned)n, (unsigned)anim.nframes, (unsigned)load_ms);
  if (strcmp(settings.last, name) != 0) { pov::strlcpy_(settings.last, name, sizeof settings.last); settings_save(); }
}

static uint32_t hold_ticks(uint16_t fi) {
  uint32_t rev = hall.rev_us ? hall.rev_us : 266667;
  uint32_t tick_us = rev / POV_K_PASSES;
  uint32_t frame_us = 10000000UL / (anim.fps_x10 ? anim.fps_x10 : 150);
  uint32_t ticks = std::max(1UL, (unsigned long)((frame_us + tick_us / 2) / tick_us));
  return ticks * (anim.frame_hold[fi] ? anim.frame_hold[fi] : 1);
}

static inline void player_wait(uint32_t ms) { ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(ms)); }   // a request wakes it

// Loads requested animations, re-fits the cap when the brightness changes, and advances frames on refresh ticks
// (1/8 revolution): the next frame is decoded into the spare buffer one tick before it is due; the column task swaps it
// in at the tick boundary (no tearing between the 24 strips).
static void player_task(void*) {
  uint16_t fi = 0;
  uint32_t due = 0, gen = 0;
  for (;;) {
    if (req_pending) {
      char name[32];
      portENTER_CRITICAL(&req_mux);
      memcpy(name, req_name, sizeof name);
      req_pending = false;
      portEXIT_CRITICAL(&req_mux);
      do_load(name);
      due = 0;
      continue;
    }
    if (refit_pending) {                                       // brightness changed: no re-decode, the worst case is cached
      refit_pending = false;
      if (anim.file && play_mode == MODE_ANIM)
        publish_palette(anim.pal_rgb, anim.npal, pov::fit_gb(anim_worst_ma31, settings.gb, CAP_MA));
    }
    if (play_mode != MODE_ANIM || !anim.file || !running) { player_wait(20); due = 0; continue; }
    if (gen != anim_gen) { gen = anim_gen; fi = 0; due = 0; }
    if (anim.nframes <= 1) { player_wait(50); continue; }
    uint32_t tc = tick_count;
    if (due == 0) due = tc + hold_ticks(fi);
    if ((int32_t)(tc - (due - 1)) < 0) { player_wait(1); continue; }
    uint16_t nf = (uint16_t)(fi + 1);
    if (nf >= anim.nframes) { if (!anim.loop) { player_wait(50); continue; } nf = 0; }
    if (frame_ready) { player_wait(1); continue; }  // the previous frame has not been swapped in yet
    if (pova_decode(anim, nf, tmp_frame)) stage_frame(tmp_frame);
    fi = nf;
    due += hold_ticks(fi);
  }
}

// ---------------------------------------------------------------- captions, text scroller, live frames (core 0)
static void publish_caption_palette() {
  uint8_t rgb[3][3];
  captions.palette_rgb(rgb);
  publish_palette(rgb, 3, captions.gb);
}

// Woken by the column task at every refresh tick (NOTIFY_TICK) and by the WebSocket handler when a caption message
// arrives (NOTIFY_MSG): renders into stage_buf and stages it for the next tick swap.
static void render_task(void*) {
  uint8_t last_gb = 0, last_rgb_c[3] = {0, 0, 0}; float last_dim = -1;
  uint8_t pat_rgb[POV_MAX_PAL][3];
  for (;;) {
    uint32_t bits = 0;
    xTaskNotifyWait(0, 0xFFFFFFFFu, &bits, portMAX_DELAY);
    bool tick = (bits & NOTIFY_TICK) != 0;
    if (tick_swapped) {                                      // the frame staged last time is on the LEDs now: ack it
      tick_swapped = false;
      for (int i = 0; i < n_staged; i++) {
        char a[64];
        snprintf(a, sizeof a, "{\"ack\":%u,\"swap_us\":%lld}", (unsigned)staged_ids[i], (long long)tick_swap_us);
        ws.textAll(a);
      }
      n_staged = 0;
    }
    if (!running) continue;
    double now = esp_timer_get_time() / 1e6;
    uint32_t rev = hall.rev_us ? hall.rev_us : 266667;
    double dt = tick ? (rev / POV_K_PASSES) / 1e6 : 0.0;
    if (play_mode == MODE_CAPTIONS) {
      captions.render(now, dt, stage_buf);
      for (int i = 0; i < captions.n_applied && n_staged < 8; i++) staged_ids[n_staged++] = captions.applied_ids[i];
      bool pal_changed = captions.gb != last_gb || captions.cfg.dim != last_dim || memcmp(captions.cfg.rgb, last_rgb_c, 3) != 0;
      if (pal_changed) { publish_caption_palette(); last_gb = captions.gb; last_dim = captions.cfg.dim; memcpy(last_rgb_c, captions.cfg.rgb, 3); }
      stage_frame(stage_buf);
    } else if (play_mode == MODE_TEXT && tick) {
      int npal = scroller.render(dt, stage_buf, pat_rgb);
      uint16_t duty[POV_MAX_PAL];
      pov::palette_duty(pat_rgb, npal, duty);
      uint8_t gb = capped_gb(stage_buf, duty);
      if (gb != cur_gb) publish_palette(pat_rgb, npal, gb);
      stage_frame(stage_buf);
    }
  }
}

static void start_text(const char* text, const uint8_t rgb[3], double cps, bool big, uint8_t vs, uint32_t secs) {
  cancel_load();
  memcpy(scroller.rgb, rgb, 3);
  scroller.big = big;
  scroller.vs = vs;
  scroller.set(text, cps);
  uint8_t pat_rgb[POV_MAX_PAL][3];
  int npal = scroller.render(0, stage_buf, pat_rgb);
  show_pattern_frame(stage_buf, pat_rgb, npal);
  text_until_ms = secs ? millis() + secs * 1000 : 0;
  play_mode = MODE_TEXT;
}

static bool start_pattern(const char* name) {
  uint8_t pat_rgb[POV_MAX_PAL][3];
  int npal = pat::by_name(name, stage_buf, pat_rgb);
  if (!npal) return false;
  cancel_load();
  show_pattern_frame(stage_buf, pat_rgb, npal);
  play_mode = MODE_PATTERN;
  return true;
}

// ---------------------------------------------------------------- OTA pause (review 2026-11-14)
// Every OTA path pauses the display first: the LEDs go dark, the simulator stops, the player idles and live sockets
// close, and the radio gets its full 19.5 dBm. On 11-14 three ArduinoOTA tries failed while an animation ran with the
// simulator at 150 rpm (66 % ping loss); with the display stopped the same OTA took 61 s.
static void apply_tx_power() { if (!ota_active && !paused) WiFi.setTxPower((wifi_power_t)settings.tx_qdbm); }

static void display_pause(uint32_t secs) {
  if (!paused) sim_before_pause = sim_rpm ? sim_rpm : (uint32_t)sim_resume_rpm;
  paused = true;
  sim_resume_rpm = 0;
  set_sim_rpm(0);
  pause_until_ms = secs ? millis() + secs * 1000 : 0;
  povota::radio_for_ota();
}

static void display_resume() {
  if (!paused) return;
  paused = false;
  pause_until_ms = 0;
  if (sim_before_pause) set_sim_rpm(sim_before_pause);
  sim_before_pause = 0;
  apply_tx_power();
}

// ---------------------------------------------------------------- WebSocket
// Open client ids, kept here (async_tcp task only). AsyncWebSocket::closeAll() iterates its client list while each
// close() can erase the node it stands on (the TCP close runs the disconnect callback synchronously): closing by id
// looks every client up afresh. Only ever called from the async_tcp task (no other task touches a socket's lifetime).
static uint32_t ws_ids[8]; static uint8_t ws_n = 0;
static void ws_close_all() {
  uint32_t ids[8]; uint8_t n = ws_n;
  memcpy(ids, ws_ids, sizeof ids);
  for (uint8_t i = 0; i < n; i++) ws.close(ids[i]);
}
// text {"cap":...} -> captions, {"live":...} -> live-frame mode (+ palette); binary 4032 B -> a live frame.
// Senders: one frame per WebSocket message, and no faster than the link carries (~20-40 KB/s in the sled: 5-10 frames/s).
// tools/pov_stream.py paces itself on the board's acks and closes without a close handshake (see the review, 3.2).
static void on_ws(AsyncWebSocket*, AsyncWebSocketClient* client, AwsEventType type, void* arg, uint8_t* data, size_t len) {
  if (type == WS_EVT_CONNECT) {
    POV_OP(OP_WS_EVENT);
    client->client()->setNoDelay(true);                      // no Nagle: 40-byte messages go now
    if (ws_n < 8) ws_ids[ws_n++] = client->id();
    return;
  }
  if (type == WS_EVT_DISCONNECT) {
    for (uint8_t i = 0; i < ws_n; i++) if (ws_ids[i] == client->id()) { ws_ids[i] = ws_ids[--ws_n]; break; }
    return;
  }
  if (type != WS_EVT_DATA) return;
  AwsFrameInfo* info = (AwsFrameInfo*)arg;
  static uint8_t live_buf[POV_FRAME_PIXELS];
  if (info->opcode == WS_BINARY) {                           // live frame, possibly split over TCP segments
    POV_OP(OP_WS_BIN);
    if (play_mode != MODE_LIVE || paused) return;
    if (info->index + len <= sizeof live_buf) memcpy(live_buf + info->index, data, len);
    if (info->final && info->index + len == info->len) {
      if (info->len != POV_FRAME_PIXELS) { live_bad = live_bad + 1; return; }
      for (int p = 0; p < POV_FRAME_PIXELS; p++) if (live_buf[p] >= live_npal) live_buf[p] = 0;
      uint8_t gb = pov::fit_gb(pov::worst_column_ma(live_buf, live_duty, 31), settings.gb, CAP_MA);
      if (gb != live_gb) { live_gb = gb; publish_palette(live_rgb, live_npal, gb); }
      stage_frame(live_buf);
      live_frames = live_frames + 1;
    }
    return;
  }
  if (!(info->final && info->index == 0 && info->len == len)) return;   // caption messages are tiny: one frame
  POV_OP(OP_WS_TEXT);
  if (len > 6 && !memcmp(data, "{\"cap\"", 6)) {
    cancel_load();
    if (play_mode != MODE_CAPTIONS) { play_mode = MODE_CAPTIONS; publish_caption_palette(); }
    captions.receive((const char*)data, len);
    if (render_task_h) xTaskNotify(render_task_h, NOTIFY_MSG, eSetBits);   // render now; it shows at the next tick
  } else if (len > 7 && !memcmp(data, "{\"live\"", 7)) {
    JsonDocument d;
    if (deserializeJson(d, data, len)) return;
    cancel_load();
    if (d["pal"].is<JsonArray>()) {
      JsonArray p = d["pal"];
      live_npal = 0;
      for (JsonVariant e : p) {
        if (live_npal >= POV_MAX_PAL) break;
        for (int c = 0; c < 3; c++) live_rgb[live_npal][c] = (uint8_t)(e[c] | 0);
        live_npal++;
      }
      if (live_npal < 2) { live_npal = 2; memset(live_rgb[0], 0, 3); memset(live_rgb[1], 255, 3); }
      pov::palette_duty(live_rgb, live_npal, live_duty);
      live_gb = settings.gb;
      publish_palette(live_rgb, live_npal, live_gb);
    } else if (live_npal == 0) {
      live_npal = 2; memset(live_rgb[0], 0, 3); memset(live_rgb[1], 255, 3);
      pov::palette_duty(live_rgb, live_npal, live_duty);
      live_gb = settings.gb;
      publish_palette(live_rgb, live_npal, live_gb);
    }
    play_mode = MODE_LIVE;
    if (d["ack"].is<int>()) {                               // {"live":1,"ack":n}: answer so a sender can pace itself
      char a[48];
      snprintf(a, sizeof a, "{\"live_ack\":%d,\"frames\":%u}", d["ack"].as<int>(), (unsigned)live_frames);
      client->text(a);
    }
  }
}

// ---------------------------------------------------------------- web API
static bool authed(AsyncWebServerRequest* r) {
  // Home LAN: a shared token in a custom header (or ?token= for forms and WebSocket upgrades) on every mutating
  // request blocks CSRF from any page on the LAN. No token configured = open (bench; the case on 2026-11-14).
  api_reqs = api_reqs + 1;
  if (strlen(POV_TOKEN) == 0) return true;
  if (r->hasHeader("X-POV-Token") && r->header("X-POV-Token") == POV_TOKEN) return true;
  return r->hasParam("token") && r->getParam("token")->value() == POV_TOKEN;
}

static uint32_t stack_free(TaskHandle_t t) { return t ? (uint32_t)uxTaskGetStackHighWaterMark(t) : 0; }

static String status_json() {
  POV_OP(OP_STATUS);
  if (!async_h) async_h = xTaskGetCurrentTaskHandle();     // status is served from the async_tcp task
  JsonDocument d;
  pov::HallSnap h = pov::snapshot(hall);
  d["fw"] = POV_FW_VERSION;
  d["elf"] = povota::elf_sha(); d["ota"] = povota::state_name(); d["ota_active"] = (bool)ota_active;
  d["mode"] = MODE_NAMES[play_mode];
  d["rpm"] = h.rev_us ? 60e6 / h.rev_us : 0.0;
  d["period_us"] = h.rev_us; d["valid"] = h.valid; d["running"] = running;
  d["pulses"] = h.pulses; d["rejected"] = h.rejected; d["resyncs"] = h.resyncs;
  d["cols"] = cols_drawn; d["late_cols"] = late_cols; d["skipped_cols"] = skipped_cols;
  d["build_us_max"] = build_us_max; d["spi_fail"] = spi_fail; d["ticks"] = tick_count;
  d["gb"] = settings.gb; d["gb_used"] = cur_gb; d["cap_ma"] = CAP_MA;
  d["offset_x8"] = settings.offset_x8; d["dir"] = settings.dir; d["autoplay"] = settings.autoplay;
  d["front_only"] = settings.front_only; d["front_deg"] = settings.front_deg;
  bool have_anim = anim.file != nullptr;
  d["anim"] = have_anim ? anim.name : ""; d["scope"] = have_anim ? anim.scope : ""; d["frames"] = have_anim ? anim.nframes : 0;
  d["last"] = settings.last;
  d["cap_gb"] = captions.gb; d["cap_peak_ma"] = captions.peak_ma; d["cap_mode"] = captions.is_tick() ? "tick" : "word";
  d["heap"] = ESP.getFreeHeap(); d["heap_min"] = ESP.getMinFreeHeap(); d["psram"] = ESP.getPsramSize();
  d["heap_max_block"] = (uint32_t)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
  d["arena"] = arena ? POVA_MAX_FILE : 0;
  d["sim_rpm"] = sim_rpm; d["sim_saved"] = settings.sim_rpm; d["sim_yielded"] = sim_resume_rpm != 0;
  d["real_pulses"] = real_hall.pulses;
  d["paused"] = (bool)paused;
  d["pause_left_s"] = (paused && pause_until_ms) ? (int32_t)(pause_until_ms - millis()) / 1000 : 0;
  d["boot_count"] = boot_count; d["reset_reason"] = reset_reason; d["reset"] = povcrash::reset_name(reset_reason);
  d["ip"] = WiFi.localIP().toString(); d["rssi"] = WiFi.RSSI(); d["uptime_s"] = (uint32_t)(esp_timer_get_time() / 1000000);
  JsonObject ld = d["load"].to<JsonObject>();
  ld["state"] = LOAD_NAMES[load_state]; ld["name"] = load_name; ld["err"] = load_err; ld["ms"] = load_ms;
  ld["ok"] = loads_ok; ld["failed"] = loads_failed;
  JsonObject w = d["wifi"].to<JsonObject>();
  w["tx_dbm"] = (int)WiFi.getTxPower() / 4.0; w["tx_dbm_set"] = settings.tx_qdbm / 4.0; w["channel"] = WiFi.channel();
  w["disconnects"] = wifi_disc; w["last_reason"] = wifi_last_reason; w["ws_clients"] = ws.count();
  JsonObject g = d["diag"].to<JsonObject>();
  g["col_busy_pct"] = col_busy_pct_x10 / 10.0;
  g["lag0_ms"] = lag0_win_us / 1000.0; g["lag0_max_ms"] = lag0_max_us / 1000.0;
  g["lag1_ms"] = lag1_win_us / 1000.0; g["lag1_max_ms"] = lag1_max_us / 1000.0;
  g["test_dark"] = (bool)test_dark; g["test_nospi"] = (bool)test_nospi;
  g["live_frames"] = live_frames; g["live_bad"] = live_bad; g["api_reqs"] = api_reqs;
  g["fs_free"] = fs_free;
  JsonObject sf = g["stack_free"].to<JsonObject>();
  sf["column"] = stack_free(col_task); sf["player"] = stack_free(player_h); sf["render"] = stack_free(render_task_h);
  sf["probe"] = stack_free(probe_h); sf["loop"] = stack_free(loop_h); sf["async_tcp"] = stack_free(async_h);
  JsonObject c = d["crash"].to<JsonObject>();
  c["count"] = povcrash::n_crashes;
  if (povcrash::have_rec) {
    c["reason"] = povcrash::last_rec.reason; c["msg"] = povcrash::last_rec.msg; c["task"] = povcrash::last_rec.task;
    c["boot"] = povcrash::last_rec.boot;
  }
  String s; serializeJson(d, s); return s;
}

static String crash_json() {
  JsonDocument d;
  const povcrash::Rec& r = povcrash::last_rec;
  d["count"] = povcrash::n_crashes;
  d["have"] = povcrash::have_rec;
  if (povcrash::have_rec) {
    char hex[12];
    d["reset"] = povcrash::reset_name(r.reset_reason); d["reset_reason"] = r.reset_reason;
    d["reason"] = r.reason; d["msg"] = r.msg; d["task"] = r.task; d["core"] = r.core;
    snprintf(hex, sizeof hex, "0x%08x", (unsigned)r.pc); d["pc"] = hex;
    JsonArray bt = d["bt"].to<JsonArray>();
    for (int i = 0; i < r.nbt && i < 16; i++) { snprintf(hex, sizeof hex, "0x%08x", (unsigned)r.bt[i]); bt.add(hex); }
    d["bt_corrupt"] = r.corrupt != 0;
    d["uptime_ms"] = r.uptime_ms; d["heap"] = r.heap; d["boot"] = r.boot; d["elf"] = r.elf;
    d["op"] = r.op < povcrash::OP_COUNT ? povcrash::OP_NAMES[r.op] : "?"; d["op_age_ms"] = r.op_age_ms;
  }
  d["running_elf"] = povota::elf_sha(); d["boot_count"] = boot_count;
  String s; serializeJson(d, s); return s;
}

// A small built-in page so a phone can change the picture before the real UI exists in /www (QA M7)
static const char INDEX_HTML[] PROGMEM = R"HTML(<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>POV column</title><style>body{font-family:sans-serif;max-width:480px;margin:16px auto;padding:0 12px}button,input,select{font-size:1em;margin:3px}
pre{background:#eee;padding:6px;font-size:.8em;white-space:pre-wrap}</style></head><body><h2>POV LED Column</h2>
<pre id=st>...</pre><div id=anims></div>
<p>Brightness <input id=gb type=range min=1 max=31 value=31 onchange="post('/api/settings',{gb:+this.value})">
<br>Offset <button onclick="trim(-8)">-1 col</button><button onclick="trim(-1)">-1/8</button><button onclick="trim(1)">+1/8</button><button onclick="trim(8)">+1 col</button>
<button onclick="post('/api/settings',{dir:-D})">flip dir</button></p>
<p>Sim hall <input id=sim size=4 placeholder=rpm><button onclick="post('/api/settings',{sim_rpm:+sim.value||0,sim_persist:true})">set + keep</button>
<button onclick="post('/api/reboot',{})">reboot</button></p>
<p>Pattern <select id=pat><option>rowramp<option>colramp<option>sets<option>grid<option>f<option>strips<option>white</select>
<button onclick="post('/api/pattern',{name:pat.value})">show</button> <button onclick="post('/api/stop',{})">stop</button></p>
<p><input id=txt placeholder="text" size=24><button onclick="post('/api/text',{text:txt.value})">scroll</button></p>
<p><input id=file type=file accept=.pova><button onclick="up()">upload</button> <a href=/update>firmware update</a> <a href=/api/crash>last crash</a></p>
<script>var T=new URLSearchParams(location.search).get('token')||'',D=1,O=0;
function hdr(){return {'Content-Type':'application/json','X-POV-Token':T}}
function post(u,b){return fetch(u,{method:'POST',headers:hdr(),body:JSON.stringify(b)}).then(r=>r.text()).then(t=>{st.textContent=t;list()})}
function trim(d){O+=d;post('/api/settings',{offset_x8:O})}
function list(){fetch('/api/anims').then(r=>r.json()).then(a=>{anims.innerHTML=a.map(x=>'<button onclick="post(\'/api/play\',{name:\''+x.name+'\'})">'+x.name+'</button> ('+x.bytes+' B) <button onclick="del(\''+x.name+'\')">x</button><br>').join('')})}
function del(n){fetch('/api/anims?name='+n,{method:'DELETE',headers:hdr()}).then(list)}
function up(){var f=file.files[0];if(!f)return;var fd=new FormData();fd.append('file',f,f.name);fetch('/api/anims',{method:'POST',headers:{'X-POV-Token':T},body:fd}).then(r=>r.text()).then(t=>{st.textContent=t;list()})}
function stat(){fetch('/api/status').then(r=>r.json()).then(j=>{st.textContent=JSON.stringify(j,null,1);D=j.dir;O=j.offset_x8;gb.value=j.gb})}
list();stat();setInterval(stat,3000);</script></body></html>)HTML";

static const char UPDATE_HTML[] PROGMEM = R"HTML(<!doctype html><html><body><h3>POV firmware update</h3>
<p>Pigtail unplugged? OTA works with the rotor closed; the column goes dark while flashing. Upload .pio/build/pov/firmware.bin</p>
<form method=POST enctype=multipart/form-data><input type=file name=fw accept=.bin><input type=submit value=flash></form></body></html>)HTML";

// ---- animation upload (review 2026-11-14). The old handler flagged a reject with `_tempObject = (void*)1`; the web
// server free()s _tempObject when the request ends, so every rejected upload crashed the board (free() of address 1 ->
// assert in heap_caps_free -> panic, reset_reason 4, 2026-11-13). And its check malloc'd the whole file (64 KB) to
// parse it: on a fragmented heap that malloc failed and a valid file (bichon_shades_orbit, 64,312 B, CRC OK) was
// rejected as "bad file". Now: per-request state is a real malloc'd POD (the server frees it), the file is checked by
// pova_check_* as it streams in, written to a temp file and renamed into place only when complete and valid.
enum UpErr : uint8_t { UP_OK, UP_NAME, UP_BUSY, UP_FS, UP_BAD, UP_BIG, UP_NOFILE };
struct UploadCtx {                       // POD only: the server releases it with free(), no destructors run
  uint8_t err;
  bool done;
  char name[33];
  char why[56];
  uint32_t bytes;
  uint16_t frames;
  PovaCheck chk;
};
static File up_file;                                     // one upload at a time (async_tcp task only)
static AsyncWebServerRequest* up_owner = nullptr;
static const char* UP_TMP = "/anims/_upload.tmp";

static void upload_abort() {
  if (up_file) up_file.close();
  LittleFS.remove(UP_TMP);
  up_owner = nullptr;
  update_fs_free();
}

static void on_upload_chunk(AsyncWebServerRequest* r, const String& fn, size_t index, uint8_t* data, size_t len, bool final) {
  POV_OP(OP_UPLOAD);
  if (!authed(r)) return;
  UploadCtx* c = (UploadCtx*)r->_tempObject;
  if (index == 0) {
    if (c) return;                                       // a second file part in the same request: ignored
    c = (UploadCtx*)calloc(1, sizeof(UploadCtx));
    if (!c) return;                                      // answered "no memory" below
    r->_tempObject = c;
    pova_check_begin(c->chk);
    String base = fn;
    int slash = base.lastIndexOf('/');
    if (slash >= 0) base = base.substring(slash + 1);
    if (base.endsWith(".pova")) base.remove(base.length() - 5);
    pov::strlcpy_(c->name, base.c_str(), sizeof c->name);
    if (!valid_name(c->name)) { c->err = UP_NAME; return; }
    if (r->contentLength() > POVA_MAX_FILE + 2048) { c->err = UP_BIG; return; }
    if (up_owner && up_owner != r) { c->err = UP_BUSY; return; }
    LittleFS.mkdir("/anims");
    up_file = LittleFS.open(UP_TMP, "w");
    if (!up_file) { c->err = UP_FS; snprintf(c->why, sizeof c->why, "cannot create a temp file"); return; }
    up_owner = r;
    r->onDisconnect([r]() { if (up_owner == r) upload_abort(); });   // the sender went away mid-file
  }
  if (!c || c->err || up_owner != r) return;
  if (len && !pova_check_feed(c->chk, data, len)) {
    c->err = (c->chk.total > POVA_MAX_FILE) ? UP_BIG : UP_BAD;
    pov::strlcpy_(c->why, c->chk.err ? c->chk.err : "invalid", sizeof c->why);
    upload_abort();
    return;
  }
  if (len && up_file.write(data, len) != len) {
    c->err = UP_FS;
    snprintf(c->why, sizeof c->why, "storage full (%u B free)", (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
    upload_abort();
    return;
  }
  c->bytes += len;
  if (final) {
    up_file.close();
    if (!pova_check_end(c->chk)) {
      c->err = UP_BAD;
      pov::strlcpy_(c->why, c->chk.err, sizeof c->why);
      upload_abort();
      return;
    }
    String path = String("/anims/") + c->name + ".pova";
    LittleFS.remove(path);                               // rename onto an existing name: replace it
    if (!LittleFS.rename(UP_TMP, path)) { c->err = UP_FS; snprintf(c->why, sizeof c->why, "rename failed"); upload_abort(); return; }
    c->frames = c->chk.nframes;
    c->done = true;
    up_owner = nullptr;
    update_fs_free();
  }
}

static void on_upload_done(AsyncWebServerRequest* r) {
  POV_OP(OP_UPLOAD);
  if (!authed(r)) { r->send(401); return; }
  UploadCtx* c = (UploadCtx*)r->_tempObject;
  JsonDocument d;
  int code = 200;
  if (!c) { code = 400; d["error"] = "no file received (multipart field 'file'), or out of memory"; }
  else if (c->err == UP_OK && c->done) { d["ok"] = true; d["name"] = c->name; d["bytes"] = c->bytes; d["frames"] = c->frames; }
  else {
    switch (c->err) {
      case UP_NAME: code = 400; d["error"] = "bad name (1-28 chars: letters, digits, _ - .)"; break;
      case UP_BUSY: code = 409; d["error"] = "another upload is in progress"; break;
      case UP_BIG: code = 413; d["error"] = "too big (max 65536 B)"; break;
      case UP_FS: code = 507; d["error"] = String("storage: ") + c->why; break;
      default: code = 400; d["error"] = String("bad file: ") + (c->why[0] ? c->why : "incomplete upload"); break;
    }
  }
  String s; serializeJson(d, s);
  r->send(code, "application/json", s);
}

static void setup_web() {
  server.on("/", HTTP_GET, [](AsyncWebServerRequest* r) {
    if (LittleFS.exists("/www/index.html")) { r->send(LittleFS, "/www/index.html", "text/html"); return; }
    r->send(200, "text/html", INDEX_HTML);
  });
  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* r) { r->send(200, "application/json", status_json()); });
  server.on("/api/crash", HTTP_GET, [](AsyncWebServerRequest* r) { r->send(200, "application/json", crash_json()); });
  server.on("/api/crash", HTTP_DELETE, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    povcrash::clear();
    r->send(200, "application/json", "{\"ok\":true}");
  });
  server.on("/api/anims", HTTP_GET, [](AsyncWebServerRequest* r) {
    POV_OP(OP_OTHER_API);
    JsonDocument d; JsonArray a = d.to<JsonArray>();
    File dir = LittleFS.open("/anims");
    if (dir) for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
      String n = f.name();
      if (!n.endsWith(".pova")) continue;
      n.remove(n.length() - 5);
      JsonObject o = a.add<JsonObject>(); o["name"] = n; o["bytes"] = f.size();
    }
    String s; serializeJson(d, s); r->send(200, "application/json", s);
  });
  // upload: multipart "file" -> /anims/<name>.pova, checked while it streams in (see on_upload_chunk)
  server.on("/api/anims", HTTP_POST, on_upload_done, on_upload_chunk);
  server.on("/api/anims", HTTP_DELETE, [](AsyncWebServerRequest* r) {
    POV_OP(OP_OTHER_API);
    if (!authed(r)) { r->send(401); return; }
    if (!r->hasParam("name") || !valid_name(r->getParam("name")->value().c_str())) { r->send(400); return; }
    String path = "/anims/" + r->getParam("name")->value() + ".pova";
    bool ok = LittleFS.remove(path);
    update_fs_free();
    r->send(ok ? 200 : 404);
  });
  // play: quick checks here, the load itself runs in the player task (the async TCP task never blocks on a 64 KB read
  // + a cap pass over every frame). 200 = queued; GET /api/status "load" says when it is playing (or why not).
  server.on("/api/play", HTTP_POST, [](AsyncWebServerRequest*) {}, nullptr,
    [](AsyncWebServerRequest* r, uint8_t* data, size_t len, size_t, size_t) {
      POV_OP(OP_PLAY);
      if (!authed(r)) { r->send(401); return; }
      JsonDocument d; deserializeJson(d, data, len);
      const char* name = d["name"] | "";
      if (!valid_name(name)) { r->send(400, "application/json", "{\"error\":\"bad name\"}"); return; }
      if (!LittleFS.exists(String("/anims/") + name + ".pova")) { r->send(404, "application/json", "{\"error\":\"not found\"}"); return; }
      if (paused) display_resume();
      request_load(name);
      JsonDocument o; o["ok"] = true; o["queued"] = name;
      String s; serializeJson(o, s); r->send(200, "application/json", s);
    });
  server.on("/api/stop", HTTP_POST, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    cancel_load();
    play_mode = MODE_OFF; text_until_ms = 0; r->send(200);
  });
  server.on("/api/pattern", HTTP_POST, [](AsyncWebServerRequest*) {}, nullptr,
    [](AsyncWebServerRequest* r, uint8_t* data, size_t len, size_t, size_t) {
      POV_OP(OP_OTHER_API);
      if (!authed(r)) { r->send(401); return; }
      JsonDocument d; deserializeJson(d, data, len);
      bool ok = start_pattern(d["name"] | "");
      r->send(ok ? 200 : 404, "application/json", ok ? "{\"ok\":true}" : String("{\"error\":\"patterns: " + String(pat::NAMES) + "\"}"));
    });
  server.on("/api/text", HTTP_POST, [](AsyncWebServerRequest*) {}, nullptr,
    [](AsyncWebServerRequest* r, uint8_t* data, size_t len, size_t, size_t) {
      POV_OP(OP_OTHER_API);
      if (!authed(r)) { r->send(401); return; }
      JsonDocument d; deserializeJson(d, data, len);
      const char* text = d["text"] | "";
      if (!*text) { r->send(400); return; }
      uint8_t rgb[3] = {255, 214, 160};
      if (d["color"].is<JsonArray>()) for (int c = 0; c < 3; c++) rgb[c] = (uint8_t)(d["color"][c] | (int)rgb[c]);
      double cps = d["speed"] | 30.0;
      bool big = d["big"] | true;
      uint8_t vs = (uint8_t)pov::clampv(d["vs"] | 2, 1, 4);
      uint32_t secs = d["secs"] | 0;
      start_text(text, rgb, pov::clampv(cps, 0.0, 400.0), big, vs, secs);
      r->send(200, "application/json", "{\"ok\":true}");
    });
  // settings: sim_rpm (+ sim_persist), gb, offset_x8, dir, autoplay, front_only, front_deg, tx_dbm (saved);
  // test_dark, test_nospi (diagnostics, not saved)
  server.on("/api/settings", HTTP_POST, [](AsyncWebServerRequest*) {}, nullptr,
    [](AsyncWebServerRequest* r, uint8_t* data, size_t len, size_t, size_t) {
      POV_OP(OP_SETTINGS);
      if (!authed(r)) { r->send(401); return; }
      JsonDocument d; deserializeJson(d, data, len);
      if (d["sim_rpm"].is<int>()) {
        uint32_t rpm = (uint32_t)pov::clampv(d["sim_rpm"].as<int>(), 0, 1200);
        if (rpm && rpm < 100) rpm = 100;                   // slower than 100 rpm the scheduler blanks anyway
        sim_resume_rpm = 0;
        if (paused) sim_before_pause = rpm; else set_sim_rpm(rpm);
        if (d["sim_persist"].is<bool>()) settings.sim_rpm = d["sim_persist"].as<bool>() ? (uint16_t)rpm : 0;
      } else if (d["sim_persist"].is<bool>()) {
        settings.sim_rpm = d["sim_persist"].as<bool>() ? (uint16_t)sim_rpm : 0;
      }
      uint8_t gb_was = settings.gb;
      if (d["gb"].is<int>()) settings.gb = (uint8_t)pov::clampv(d["gb"].as<int>(), 1, 31);
      if (d["offset_x8"].is<int>()) settings.offset_x8 = (int16_t)pov::clampv(d["offset_x8"].as<int>(), -768, 768);
      if (d["dir"].is<int>()) settings.dir = d["dir"].as<int>() < 0 ? -1 : 1;
      if (d["autoplay"].is<bool>()) settings.autoplay = d["autoplay"];
      if (d["front_only"].is<bool>()) settings.front_only = d["front_only"];
      if (d["front_deg"].is<int>()) settings.front_deg = (int16_t)(((d["front_deg"].as<int>() % 360) + 360) % 360);
      if (d["tx_dbm"].is<float>() || d["tx_dbm"].is<int>()) {
        settings.tx_qdbm = (uint8_t)pov::clampv((int)lroundf(d["tx_dbm"].as<float>() * 4), 8, 78);
        apply_tx_power();
      }
      bool dark_was = test_dark;
      if (d["test_dark"].is<bool>()) test_dark = d["test_dark"].as<bool>();
      if (d["test_nospi"].is<bool>()) test_nospi = d["test_nospi"].as<bool>();
      if (test_dark != dark_was) publish_palette(last_rgb, last_npal, last_gb_req);   // re-apply the current colours
      settings_save();
      if (settings.gb != gb_was && player_h) { refit_pending = true; xTaskNotifyGive(player_h); }   // cached worst case
      r->send(200, "application/json", status_json());
    });
  // OTA prep: pause the display (LEDs dark, simulator off, live sockets closed, full TX power) for up to ?secs=N
  // (default 180, 0 = until reboot). tools/ota_flash.py calls it before every update; POST /api/resume undoes it.
  server.on("/api/ota-prep", HTTP_POST, [](AsyncWebServerRequest* r) {
    POV_OP(OP_OTHER_API);
    if (!authed(r)) { r->send(401); return; }
    uint32_t secs = OTA_PREP_DEFAULT_S;
    if (r->hasParam("secs")) secs = (uint32_t)pov::clampv((int)r->getParam("secs")->value().toInt(), 0, 900);
    display_pause(secs);
    ws_close_all();
    JsonDocument d;
    d["ok"] = true; d["paused_s"] = secs; d["rssi"] = WiFi.RSSI(); d["heap"] = ESP.getFreeHeap();
    d["heap_max_block"] = (uint32_t)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT); d["ota"] = povota::state_name();
    String s; serializeJson(d, s); r->send(200, "application/json", s);
  });
  server.on("/api/resume", HTTP_POST, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    display_resume();
    r->send(200, "application/json", "{\"ok\":true}");
  });
  // Reboot without opening the sled. Refused while a fresh OTA image is still "pending" (the first ~15 s after an OTA
  // boot): a reset then makes the bootloader roll back to the previous image. ?force=1 overrides.
  server.on("/api/reboot", HTTP_POST, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    bool force = r->hasParam("force") && r->getParam("force")->value() == "1";
    if (!force && povota::pending_verify()) {
      r->send(409, "application/json", "{\"error\":\"new OTA image not confirmed yet (~15 s after boot): a reset now rolls it back. Retry shortly, or ?force=1\"}");
      return;
    }
    paused = true;                                       // LEDs dark before the reset
    AsyncWebServerResponse* resp = r->beginResponse(200, "application/json", "{\"ok\":true,\"rebooting\":true}");
    resp->addHeader("Connection", "close");
    r->send(resp);
    reboot_at_ms = millis() + 400;
  });
  // firmware update from a browser (Update.h, no extra library); ArduinoOTA covers pio run -t upload
  server.on("/update", HTTP_GET, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    r->send(200, "text/html", UPDATE_HTML);
  });
  // OTA review 2026-11-13: the server drops a request after 3 s without data and sends nothing (curl rc 52); a dropped
  // upload used to leave Update running and ota_active set (column dark, every later update "already running").
  server.on("/update", HTTP_POST, [](AsyncWebServerRequest* r) {
    if (!authed(r)) { r->send(401); return; }
    bool ok = http_ota_ok && !Update.hasError() && !Update.isRunning();
    String msg = ok ? String("OK, rebooting") : String("update failed: ") + Update.errorString();
    AsyncWebServerResponse* resp = r->beginResponse(ok ? 200 : 500, "text/plain", msg);
    resp->addHeader("Connection", "close");
    r->send(resp);
    if (ok) reboot_at_ms = millis() + 500;
    else { ota_active = false; display_resume(); }
  }, [](AsyncWebServerRequest* r, String, size_t index, uint8_t* data, size_t len, bool final) {
    POV_OP(OP_HTTP_OTA);
    if (!authed(r)) return;
    if (index == 0) {
      r->client()->setRxTimeout(30);                 // ride out Wi-Fi stalls instead of the server's 3 s
      if (Update.isRunning()) Update.abort();        // a stale, dropped upload
      display_pause(0);
      ota_active = true;
      http_ota_ok = Update.begin(UPDATE_SIZE_UNKNOWN);
      r->onDisconnect([]() {                         // also runs after a good upload: then reboot_at_ms is set
        if (Update.isRunning()) Update.abort();
        if (!reboot_at_ms) { ota_active = false; display_resume(); }
      });
    }
    if (http_ota_ok && len && Update.write(data, len) != len) http_ota_ok = false;
    if (final && http_ota_ok) http_ota_ok = Update.end(true);
  });
  // WebSocket (captions, live frames); the same token on the upgrade request (header or ?token=)
  ws.onEvent(on_ws);
  ws.setFilter([](AsyncWebServerRequest* r) { return !ota_active && !paused && authed(r); });   // none mid-update
  server.addHandler(&ws);
  server.serveStatic("/", LittleFS, "/www/").setDefaultFile("index.html");
  server.onNotFound([](AsyncWebServerRequest* r) { r->send(404, "text/plain", "not found"); });
  server.begin();
}

// ---------------------------------------------------------------- diagnostics probe (core 0, lowest user priority)
// Wakes every 10 ms and records how late it was: if core 0 were starved by the display path (as suspected on 11-14),
// this lag would grow to tens or hundreds of ms. Also turns the column task's busy time into a percentage.
static void probe_task(void*) {
  uint32_t win_max = 0; int64_t win_start = esp_timer_get_time(), last_pct = win_start; uint32_t last_busy = col_busy_us;
  for (;;) {
    int64_t t0 = esp_timer_get_time();
    vTaskDelay(pdMS_TO_TICKS(10));
    int64_t t1 = esp_timer_get_time();
    int64_t lag = t1 - t0 - 10000;
    uint32_t l = lag > 0 ? (uint32_t)lag : 0;
    if (l > win_max) win_max = l;
    if (l > lag0_max_us) lag0_max_us = l;
    if (t1 - win_start > 5000000) { lag0_win_us = win_max; win_max = 0; win_start = t1; }
    if (t1 - last_pct >= 1000000) {
      uint32_t b = col_busy_us;
      col_busy_pct_x10 = (uint32_t)((uint64_t)(b - last_busy) * 1000 / (uint64_t)(t1 - last_pct));
      last_busy = b; last_pct = t1;
    }
  }
}

// ArduinoOTA has authenticated and the image transfer starts (runs inside ArduinoOTA.handle() in loop()): pause the
// display for the rest of the update. Sockets are not closed from here (loop task): /api/ota-prep closes them earlier.
static void ota_begin_hook() {
  povcrash::cur_op = povcrash::OP_ARDUINO_OTA; povcrash::cur_op_ms = millis();
  display_pause(0);
  ota_active = true;
}

// ---------------------------------------------------------------- setup / loop
void setup() {
  delay(300);                                           // let the bank + pigtail settle before any load (as phase0)
  Serial.begin(115200);
  reset_reason = (int)esp_reset_reason();
  if (reset_reason == ESP_RST_POWERON) boot_count = 0;
  boot_count++;
  Serial.printf("boot %u, reset reason %d (%s)\n", (unsigned)boot_count, reset_reason, povcrash::reset_name(reset_reason));
  povcrash::begin(reset_reason, boot_count);            // store a crash record from the previous run, arm the hook
  settings_load();
  memset(frame_buf, 0, sizeof frame_buf);
  for (int ch = 0; ch < 2; ch++) pov::build_blank(blank_buf[ch]);
  uint8_t off[1][3] = {{0, 0, 0}};
  pov::make_palette(pal_set[0], off, 1, 0);
  pov::make_palette(pal_set[1], off, 1, 0);
  setup_spi(SPI3_HOST, PIN_D0, PIN_C0, &spi_dev[0]);   // VSPI: IO_MUX pins 23 / 18
  setup_spi(SPI2_HOST, PIN_D1, PIN_C1, &spi_dev[1]);   // HSPI: IO_MUX pins 13 / 14
  blank_all();                                          // every LED off before anything else (the strips power up random)
#ifdef POV_OTA_CRASH_TEST
  abort();                                              // env pov_crashtest: the rollback self-test image (never stays)
#endif
  LittleFS.begin(true, "/littlefs", 10, "littlefs");   // partition label is "littlefs" (partitions.csv), not the default "spiffs"
  // the animation arena first, while the heap is still in one piece (64 KB contiguous)
  arena = (uint8_t*)heap_caps_malloc(POVA_MAX_FILE, MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL);
  if (!arena) Serial.println("no memory for the animation arena: animations cannot play");
  LittleFS.remove(UP_TMP);                              // an upload cut off by a reset
  update_fs_free();
  captions.begin();
  loop_h = xTaskGetCurrentTaskHandle();
  // the column engine first: it never waits for Wi-Fi
  xTaskCreatePinnedToCore(column_task, "column", 4096, nullptr, configMAX_PRIORITIES - 2, &col_task, 1);
  xTaskCreatePinnedToCore(player_task, "player", 6144, nullptr, 3, &player_h, 0);
  xTaskCreatePinnedToCore(render_task, "render", 8192, nullptr, 5, &render_task_h, 0);
  xTaskCreatePinnedToCore(probe_task, "probe", 2048, nullptr, 1, &probe_h, 0);
  // Wi-Fi on core 0 (Arduino default); 10 s for the home network, then the fallback access point
  // Bank power (2026-11-13): never came up on the bank. Hostname before mode(), reduced TX power during the join
  // (smaller current spikes through pigtail + fuse), auto-reconnect, and the AP alongside STA so it keeps retrying.
  // After the join the TX power is the saved tx_dbm (default 13 dBm, unchanged; 19.5 is the review's suggestion).
  WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
    wifi_disc = wifi_disc + 1;
    wifi_last_reason = info.wifi_sta_disconnected.reason;
  }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.setHostname("pov");
  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_13dBm);
  WiFi.setSleep(false);                                 // low caption latency (costs ~50 mA average, QA m5)
  WiFi.setAutoReconnect(true);
#ifdef POV_STATIC_IP                                    // optional (wifi_secrets.h): a fixed address instead of DHCP
  WiFi.config(IPAddress(POV_STATIC_IP), IPAddress(POV_GATEWAY), IPAddress(POV_SUBNET), IPAddress(POV_DNS));
#endif
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 150 && WiFi.status() != WL_CONNECTED; i++) delay(100);
  if (WiFi.status() != WL_CONNECTED) { WiFi.mode(WIFI_AP_STA); WiFi.softAP("POV-Column", "povcolumn"); WiFi.begin(WIFI_SSID, WIFI_PASS); }
  else apply_tx_power();
  wifi_disc = 0;                                        // count drops after the first join only
  MDNS.begin("pov"); MDNS.addService("http", "tcp", 80);
  ArduinoOTA.setHostname("pov");
  ArduinoOTA.setPassword(OTA_PASS);
  ArduinoOTA.setTimeout(povota::OTA_RX_TIMEOUT_MS);   // default 1 s x 3 tries: one lost packet aborted the update
  ArduinoOTA.onStart([]() { ota_begin_hook(); });
  ArduinoOTA.onEnd([]() { ota_active = false; });
  ArduinoOTA.onError([](ota_error_t) { ota_active = false; display_resume(); });
  ArduinoOTA.begin();
  setup_web();
  // scroll the address for 10 s, then autoplay the last animation; a saved simulator rpm starts now (so the address
  // shows with the motor off, and nobody has to open the sled to set it again after a reboot)
  String ip = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : WiFi.softAPIP().toString();
  uint8_t warm[3] = {255, 214, 160};
  start_text((ip + "  POV.LOCAL  ").c_str(), warm, 30.0, true, 2, BOOT_TEXT_MS / 1000);
  if (settings.sim_rpm) set_sim_rpm(settings.sim_rpm);
  Serial.printf("POV v2 %s up: ip %s, heap %u (largest %u), arena %s, sim %u rpm, cap %u mA, last '%s'\n", POV_FW_VERSION,
                ip.c_str(), (unsigned)ESP.getFreeHeap(), (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT),
                arena ? "64 KB" : "MISSING", (unsigned)settings.sim_rpm, (unsigned)CAP_MA, settings.last);
}

// The simulator steps aside while the real sensor reports a steady rotation (two periods agreeing within 5 %, last
// pulse < 1 s ago) and comes back 2 s after the real pulses stop. Noise on the hall lead cannot pass that test.
static void sim_yield_poll(int64_t now_us) {
  if (paused) return;
  if (sim_rpm) {
    pov::HallSnap r = pov::snapshot(real_hall);
    if (r.valid && now_us - r.t < 1000000) {
      uint32_t was = sim_rpm;
      set_sim_rpm(0);
      sim_resume_rpm = was;
      Serial.printf("real hall at %.0f rpm: simulator (%u rpm) off\n", r.rev_us ? 60e6 / r.rev_us : 0.0, (unsigned)was);
    }
  } else if (sim_resume_rpm) {
    pov::HallSnap h = pov::snapshot(hall);
    if (h.t == 0 || now_us - h.t > 2000000) {
      uint32_t rpm = sim_resume_rpm;
      sim_resume_rpm = 0;
      set_sim_rpm(rpm);
      Serial.printf("real hall stopped: simulator back at %u rpm\n", (unsigned)rpm);
    }
  }
}

void loop() {
  static int64_t last_us = 0, win_start = 0;
  static uint32_t win_max = 0, last_clean = 0, last_sim = 0;
  int64_t now_us = esp_timer_get_time();
  if (last_us) {                                        // loop() gap beyond its own 5 ms delay: core-1 starvation
    int64_t gap = now_us - last_us - 5000;
    uint32_t g = gap > 0 ? (uint32_t)gap : 0;
    if (g > win_max) win_max = g;
    if (g > lag1_max_us && now_us > 20000000) lag1_max_us = g;   // ignore the boot (Wi-Fi join, LittleFS mount)
    if (now_us - win_start > 5000000) { lag1_win_us = win_max; win_max = 0; win_start = now_us; }
  }
  ArduinoOTA.handle();
  povota::guard_poll(WiFi.status() == WL_CONNECTED);   // confirm or roll back a fresh OTA image
  uint32_t now = millis();
  if (text_until_ms && play_mode == MODE_TEXT && (int32_t)(now - text_until_ms) >= 0) {
    text_until_ms = 0;
    if (settings.autoplay && settings.last[0] && valid_name(settings.last)) request_load(settings.last);
    else play_mode = MODE_OFF;
  }
  if (paused && pause_until_ms && (int32_t)(now - pause_until_ms) >= 0 && !ota_active) {
    Serial.println("OTA prep timed out without an update: display back on");
    display_resume();
  }
  if (now - last_sim >= 250) { last_sim = now; sim_yield_poll(now_us); }
  if (now - last_clean > 5000) { last_clean = now; ws.cleanupClients(); }   // forgets closed clients only (< 8 open)
  if (reboot_at_ms && (int32_t)(now - reboot_at_ms) >= 0) {
    blank_all();
    delay(20);
    ESP.restart();
  }
  last_us = esp_timer_get_time();
  delay(5);
}
