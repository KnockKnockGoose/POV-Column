// pov_crash.h - crash recorder for the image firmware (Wi-Fi control review 2026-11-14,
// docs/2026-11-14-wifi-control-review.md). Include it from src/main.cpp only.
//
// Why: the board panicked at least twice (2026-11-13 after a rejected upload, 2026-11-14 during live streaming) with
// the sled closed, so no serial log exists and the cause had to be found by reading code. Now every panic, watchdog
// reset or abort leaves a record that survives the reboot and a power cycle, readable over Wi-Fi:
//   GET /api/crash        reason, abort/assert message, task, core, PC + backtrace, uptime, heap, what the API was doing
//   DELETE /api/crash     forget it
//   py tools\pov_crash.py fetches it and turns the addresses into file:line with the matching firmware.elf
//
// How: arduino-esp32 3.x ships a hook, set_arduino_panic_handler(), called from its wrapper of IDF's
// esp_panic_handler(). PlatformIO's pioarduino build does NOT pass the -Wl,--wrap=esp_panic_handler flag that the
// Arduino IDE build uses, so that wrapper was silently discarded (firmware.map, "Discarded input sections");
// platformio.ini now adds the flag for env:pov. The hook writes the record into RTC memory (kept across the reset);
// the next boot copies it to NVS (kept across power-off) and serves it.
#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <algorithm>
#include <esp_heap_caps.h>
#include <esp_timer.h>
#include <esp_app_desc.h>
#include <esp_private/panic_internal.h>   // g_panic_abort, g_panic_abort_details (the abort / assert message)

namespace povcrash {

static const uint32_t MAGIC = 0x50435231;   // "PCR1"

// What our code was doing (breadcrumb): set on entry to the API handlers and the loader, cleared on exit
enum Op : uint8_t { OP_NONE, OP_WS_BIN, OP_WS_TEXT, OP_WS_EVENT, OP_UPLOAD, OP_PLAY, OP_SETTINGS, OP_STATUS, OP_LOAD,
                    OP_HTTP_OTA, OP_ARDUINO_OTA, OP_OTHER_API, OP_COUNT };
static const char* const OP_NAMES[OP_COUNT] = {"none", "ws binary frame", "ws text message", "ws connect/close",
                                                "anim upload", "play request", "settings", "status", "anim load",
                                                "/update upload", "ArduinoOTA", "other api"};

struct Rec {                 // fixed layout: NVS keeps one of these (size checked on read)
  uint32_t magic, seq;
  uint32_t pc, uptime_ms, heap, boot;
  uint8_t core, nbt, corrupt, op;
  uint32_t op_age_ms;
  uint32_t bt[16];
  char task[16];
  char reason[40];
  char msg[100];
  char elf[17];
  uint8_t reset_reason, pad[2];
};

RTC_NOINIT_ATTR static Rec rtc_rec;           // written by the panic hook, survives the reset (not a power-off)
static Rec last_rec;                          // the stored record, served by /api/crash
static bool have_rec = false;
static uint32_t n_crashes = 0;                // crashes recorded since the counter was last cleared
static char elf_id[17];
static volatile uint8_t cur_op = OP_NONE;
static volatile uint32_t cur_op_ms = 0;

struct OpScope {             // POV_OP(x): breadcrumb for the duration of a handler
  uint8_t prev;
  explicit OpScope(uint8_t op) : prev(cur_op) { cur_op = op; cur_op_ms = millis(); }
  ~OpScope() { cur_op = prev; }
};

static void copy_str(char* d, size_t n, const char* s) {
  size_t i = 0;
  if (s) for (; i + 1 < n && s[i]; i++) d[i] = s[i];
  d[i] = 0;
}

// Runs inside the panic handler (other core stalled, interrupts off): no locks, no allocation, no printf.
static void on_panic(arduino_panic_info_t* info, void*) {
  Rec& r = rtc_rec;
  r.magic = 0;
  r.seq = r.seq + 1;
  r.core = (uint8_t)info->core;
  r.pc = (uint32_t)info->pc;
  r.nbt = (uint8_t)std::min<unsigned>(info->backtrace_len, 16);
  for (int i = 0; i < r.nbt; i++) r.bt[i] = info->backtrace[i];
  r.corrupt = info->backtrace_corrupt ? 1 : 0;
  copy_str(r.reason, sizeof r.reason, info->reason);
  copy_str(r.msg, sizeof r.msg, (g_panic_abort && g_panic_abort_details) ? g_panic_abort_details : "");
  TaskHandle_t t = xTaskGetCurrentTaskHandleForCore(info->core);
  copy_str(r.task, sizeof r.task, t ? pcTaskGetName(t) : "?");
  r.uptime_ms = (uint32_t)(esp_timer_get_time() / 1000);
  r.heap = (uint32_t)heap_caps_get_free_size(MALLOC_CAP_8BIT);
  r.op = cur_op;
  r.op_age_ms = r.uptime_ms - cur_op_ms;
  copy_str(r.elf, sizeof r.elf, elf_id);
  r.magic = MAGIC;
}

// Call early in setup(), after the reset reason and the boot counter are known.
static void begin(int reset_reason, uint32_t boot_count) {
  const esp_app_desc_t* d = esp_app_get_description();
  for (int i = 0; i < 8; i++) snprintf(elf_id + 2 * i, 3, "%02x", d->app_elf_sha256[i]);
  bool crashed = reset_reason == ESP_RST_PANIC || reset_reason == ESP_RST_INT_WDT || reset_reason == ESP_RST_TASK_WDT ||
                 reset_reason == ESP_RST_WDT;
  if (reset_reason == ESP_RST_POWERON) { rtc_rec.magic = 0; rtc_rec.seq = 0; }
  Preferences p;
  p.begin("povcrash", false);
  n_crashes = p.getUInt("n", 0);
  if (crashed) {
    if (rtc_rec.magic != MAGIC) {             // the hook did not run (e.g. a watchdog the hook could not see): stub
      memset(&rtc_rec, 0, sizeof rtc_rec);
      copy_str(rtc_rec.reason, sizeof rtc_rec.reason, "reset without a panic record");
      copy_str(rtc_rec.elf, sizeof rtc_rec.elf, elf_id);
    }
    rtc_rec.boot = boot_count;
    rtc_rec.reset_reason = (uint8_t)reset_reason;
    rtc_rec.magic = MAGIC;
    p.putBytes("rec", &rtc_rec, sizeof rtc_rec);
    p.putUInt("n", ++n_crashes);
    Serial.printf("CRASH recorded: %s %s (task %s, pc 0x%08x)\n", rtc_rec.reason, rtc_rec.msg, rtc_rec.task,
                  (unsigned)rtc_rec.pc);
  }
  rtc_rec.magic = 0;                          // consumed: a later clean reset must not record it again
  have_rec = p.getBytesLength("rec") == sizeof(Rec) && p.getBytes("rec", &last_rec, sizeof last_rec) == sizeof last_rec &&
             last_rec.magic == MAGIC;
  p.end();
  set_arduino_panic_handler(on_panic, nullptr);
}

static void clear() {
  Preferences p;
  p.begin("povcrash", false);
  p.clear();
  p.end();
  have_rec = false;
  n_crashes = 0;
}

static const char* reset_name(int r) {
  switch (r) {
    case ESP_RST_POWERON: return "power-on";
    case ESP_RST_EXT: return "external pin";
    case ESP_RST_SW: return "software (restart/OTA)";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT: return "interrupt watchdog";
    case ESP_RST_TASK_WDT: return "task watchdog";
    case ESP_RST_WDT: return "other watchdog";
    case ESP_RST_DEEPSLEEP: return "deep sleep";
    case ESP_RST_BROWNOUT: return "brownout";
    default: return "other";
  }
}

}  // namespace povcrash

#define POV_OP(x) povcrash::OpScope _pov_op_scope(povcrash::x)
