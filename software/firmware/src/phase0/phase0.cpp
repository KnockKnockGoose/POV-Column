// =====================================================================================================================
//  POV LED Column v2 - phase-0 bring-up sketch (bench, USB, rotor open). Built 2026-11-03, first run on the rig 2026-11-04.
//  Matches the bring-up steps of docs/2026-11-02-electrical-design.md section 9 (steps 2-9) and the software report's
//  phase 0: one chain at a time, low brightness, test patterns in LED space, the SK9822 end-frame / last-LED check,
//  the SPI frame-time measurement, a 2.78 ms column clock, a hall-sensor readout, a current-cap test, Wi-Fi + OTA.
//  2026-11-04 (bench): run-time SPI clock (s), colour value (v), the frame re-sent every 100 ms; then the SPI
//  signal-investigation knobs (p u d z e l o r x a q) for the "right colours, wrong brightness above 1 MHz" fault.
//  Bench plan and the reasoning behind each knob: docs/2026-11-04-spi-signal-investigation.md
//  2026-11-10 (0.3): bench runs from the supply alone (5 V on J1, no USB): Wi-Fi joins at boot when src/wifi_secrets.h
//  has a real SSID (hostname pov, mDNS pov.local, ArduinoOTA), a telnet-style command port on TCP 23 (one client; a
//  new connection replaces the old one) runs the same command parser as Serial and every reply goes to both (Tee
//  `out`), several commands per line (space-separated: "cb s8000 a"), and the bench state is kept in NVS (S / R,
//  auto-saved 2 s after a change) so a power cycle comes back in the same test set-up. the laptop client: tools/pov_cmd.py
//
//  Flash:  tools\pio.cmd run -e phase0 -t upload      then  tools\pio.cmd device monitor   (115200, type ? for help)
//          the laptop (no PlatformIO): tools/FLASH-FROM-LAPTOP.md (merged image in dist/)
//
//  *** USB / bank rule (electrical report 2.7, open question E3) ***  The DevKit's VIN pin IS the 5 V bus. Pigtail
//  unplugged whenever a USB cable is in. If the diode test shows no D1 on the VIN path: never both, ever. First flash
//  the ESP32 alone on USB (bench step 2), diode-test it, only then solder it into the carrier.
//
//  Serial commands (single letters, numbers attached):                                                   [default]
//    c0 | c1 | cb   drive chain 0 (VSPI 23/18), chain 1 (HSPI 13/14) or both                             [c0]
//    nNN            LEDs per chain to light (1..168; 14 = one strip, 168 = a full chain)                    [14]
//    gNN            global brightness 1..31 (the 5-bit current field)                                     [4]
//    vNNN           colour value 0..255 for patterns 1-4 and a (before gamma)                             [255]
//    mNNNN          current cap in mA for the dense pattern (LEDs incl. 1 mA idle each)                    [1000]
//    0 off  1 red  2 green  3 blue  4 white  5 strip numbers (strip s lights its LED s)  6 row ramp (image rows)
//    7 last LED only  8 walking LED (10 per s)  9 dense white at the cap
//    y              full rainbow sliding back and forth (10 ms steps)
//    Y              the y rainbow plus a smooth brightness pulse (sine, 3 s period, 10 % .. 100 % of the colour)
//    U              patriotic: red / white / blue bands (~4.7 LEDs each on 14), sub-LED blended, eased slide back and
//                   forth over one full R-W-B period (2.6 s per pass), same 3 s pulse at 15 % .. 100 %; white at 65 %
//    a              field ladder: LED k red at v with field 1, 2, 4, 8, 16, 1, 2, ... (one field bit per LED)
//    xHHHHHHHH      raw LED frame for the first n LEDs, 4 bytes in hex: header, B, G, R; no gamma, no field
//                   logic (xE40000FF = red at field 4, xF60000FF = red at field 22)
//    sNNNN          SPI clock in kHz, 100..20000                                                         [1000]
//    pN             SPI mode 0..3: 0 and 3 change DATA on the falling CLK edge (the SK9822 samples on the
//                   rising one), 1 and 2 change it on the rising edge (diagnostic only)                    [0]
//    uNN            CLK high time, % of the period, 10..90. In modes 0/3 the LOW time is DATA's setup time
//                   before the sampling edge and the HIGH time its hold time                                [50]
//    dN             DATA (MOSI) delay after its CLK edge: 0..7 = N x 12.5 ns, 8 = half a clock period       [0]
//    zN  eN  lN     start zeros 0..16 B [4], end-frame 0xFF 0..32 B [24], latch zeros 0..8 B [4]
//    o0 | o1        the frame carries all 168 LED slots [o0] or only the n lit ones (then the end frame matters)
//    rN             send each frame N times back to back, 1..3                                           [1]
//    q              SPI set-up as the hardware holds it (clock, mode, duty, MOSI delay, IO_MUX) + frame layout
//    t   SPI frame time: 200 blocking transfers and 200 DMA-queued ones, min/avg/max us
//    k   column clock: a frame every 2,778 us for 10 s with the last LED cycling R/G/B (late count, jitter)
//    h   hall readout on/off: pulses, period, rpm, pulse width, the firmware's period estimate (A3144 on GPIO 27)
//    w   join Wi-Fi (src/wifi_secrets.h) and start ArduinoOTA (automatic at boot when the SSID is real); i   chip / heap /
//        PSRAM / pins / Wi-Fi / frame-resend stats;  ?   this help
//    S   save the bench state to NVS now (it also saves itself ~2 s after any change);  R   reset to the defaults [..]
//  The current frame is re-sent every 100 ms whatever the pattern (a strip that missed a frame catches the next one,
//  and the scope always has a burst to trigger on).
// =====================================================================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include "pov_ota.h"                           // OTA hardening (docs/2026-11-13-ota-failure-review.md)
#include <Preferences.h>
#include <driver/spi_master.h>
#include <driver/gptimer.h>
#include <esp_timer.h>
#include <soc/spi_struct.h>                    // SPI2 / SPI3 registers: the MOSI-delay knob and the q read-back

#include "povframe.h"
#include "povsched.h"

extern "C" bool spicommon_bus_using_iomux(spi_host_device_t host);   // esp_driver_spi (esp_private/spi_common_internal.h)

#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
#define WIFI_SSID "FILL_IN"
#define WIFI_PASS "FILL_IN"
#define OTA_PASS "FILL_IN"
#endif

static const int PIN_HALL = 26;  // moved from IO27 (damaged 2026-11-12)
static const int PIN_D0 = 23, PIN_C0 = 18, PIN_D1 = 13, PIN_C1 = 14;
static int SPI_HZ = 1000000;                   // sNNNN (kHz) changes it at run time (bench signal-integrity check)
static const uint32_t COL_US = 2778;
static const spi_host_device_t HOST[2] = {SPI3_HOST, SPI2_HOST};   // chain 0 = VSPI, chain 1 = HSPI
static spi_dev_t* const HW[2] = {&SPI3, &SPI2};

// The LED part of each frame is built in frame[] (the povframe.h layout: 4 B start, 168 x 4 B, end, latch); send()
// assembles what actually goes out into tx[] with the z / e / l / o settings. Longest: 16 + 672 + 32 + 8 = 728 B.
static const int TX_BYTES = 16 + 4 * POV_LEDS_PER_CHAIN + 32 + 8;
static spi_device_handle_t dev[2] = {nullptr, nullptr};
static DMA_ATTR uint8_t frame[2][POV_FRAME_BYTES];
static DMA_ATTR uint8_t tx[2][TX_BYTES];
static int tx_len[2] = {0, 0};
static int chain_sel = 0;          // 0, 1, 2 = both
static int n_leds = 14;
static uint8_t gb = 4;
static uint32_t cap_ma = 1000;
static char pattern = '0';
static uint8_t val = 255;                     // vNNN: colour value for patterns 1-4, 7, 8 (bench check of 8-bit dimming)
static int walk = 0;
static bool hall_on = false, wifi_on = false;
static uint8_t last_led_phase = 0;

// signal-investigation settings (2026-11-04)
static int spi_mode = 0;                      // pN
static int duty_pct = 50;                     // uNN: CLK high time in % of the period
static int mosi_dly = 0;                      // dN: 0..7 = N x 12.5 ns (APB cycles), 8 = half a clock period
static int start_b = 4, end_b = 4 * (POV_LEDS_PER_CHAIN / 32 + 1), latch_b = 4;   // zN eN lN (bytes)
static bool short_frame = false;              // o1: only the n lit LED slots go out
static int repeats = 1;                       // rN
static uint8_t raw4[4] = {0xE4, 0x00, 0x00, 0xFF};   // xHHHHHHHH: header, B, G, R
static uint32_t spi_err = 0;

// ---------------------------------------------------------------- output tee: Serial + the TCP client (port 23)
static WiFiServer tcp_server(23);
static WiFiClient tcp;

class Tee : public Print {
 public:
  size_t write(uint8_t c) override { return write(&c, 1); }
  size_t write(const uint8_t* buf, size_t n) override {
    Serial.write(buf, n);
    if (tcp && tcp.connected()) {                // telnet wants CR LF: add the CR printf's bare "\n" leaves out
      uint8_t tmp[128];
      size_t m = 0;
      for (size_t i = 0; i < n; i++) {
        if (buf[i] == '\n' && prev_ != '\r') tmp[m++] = '\r';
        tmp[m++] = buf[i];
        prev_ = buf[i];
        if (m >= sizeof(tmp) - 1) { tcp.write(tmp, m); m = 0; }
      }
      if (m) tcp.write(tmp, m);
    }
    return n;
  }
 private:
  uint8_t prev_ = 0;
};
static Tee out;

// ---------------------------------------------------------------- bench state in NVS (Preferences "bench" / "st")
// 18 x uint8 then 2 x uint16: no padding, so memcmp on two snapshots is exact. Bump STATE_VER when the layout changes.
static const uint8_t STATE_VER = 1;
struct BenchState {
  uint8_t ver, chain_sel, n_leds, gb, val, pattern, spi_mode, duty, mosi_dly, start_b, end_b, latch_b, short_frame, repeats;
  uint8_t raw4[4];
  uint16_t spi_khz, cap_ma;
};
static_assert(sizeof(BenchState) == 22, "BenchState must stay unpadded");

static BenchState snapshot_state() {
  BenchState s;
  memset(&s, 0, sizeof(s));
  s.ver = STATE_VER; s.chain_sel = (uint8_t)chain_sel; s.n_leds = (uint8_t)n_leds; s.gb = gb; s.val = val; s.pattern = (uint8_t)pattern;
  s.spi_mode = (uint8_t)spi_mode; s.duty = (uint8_t)duty_pct; s.mosi_dly = (uint8_t)mosi_dly;
  s.start_b = (uint8_t)start_b; s.end_b = (uint8_t)end_b; s.latch_b = (uint8_t)latch_b; s.short_frame = short_frame; s.repeats = (uint8_t)repeats;
  memcpy(s.raw4, raw4, 4);
  s.spi_khz = (uint16_t)(SPI_HZ / 1000); s.cap_ma = (uint16_t)cap_ma;
  return s;
}

static bool known_pattern(char p) { return (p >= '0' && p <= '9') || p == 'a' || p == 'b' || p == 'y' || p == 'Y' || p == 'U' || p == 'K' || p == 'x'; }

// values pass the same clamps as the commands, so a corrupt blob can't put the bench somewhere the commands couldn't
static void apply_state(const BenchState& s) {
  chain_sel = s.chain_sel <= 2 ? s.chain_sel : 0;
  n_leds = pov::clampv((int)s.n_leds, 1, (int)POV_LEDS_PER_CHAIN);
  gb = (uint8_t)pov::clampv((int)s.gb, 1, 31);
  val = s.val;
  pattern = known_pattern((char)s.pattern) ? (char)s.pattern : '0';
  spi_mode = pov::clampv((int)s.spi_mode, 0, 3);
  duty_pct = pov::clampv((int)s.duty, 10, 90);
  mosi_dly = pov::clampv((int)s.mosi_dly, 0, 8);
  start_b = pov::clampv((int)s.start_b, 0, 16); end_b = pov::clampv((int)s.end_b, 0, 32); latch_b = pov::clampv((int)s.latch_b, 0, 8);
  short_frame = s.short_frame != 0; repeats = pov::clampv((int)s.repeats, 1, 3);
  memcpy(raw4, s.raw4, 4);
  SPI_HZ = pov::clampv((int)s.spi_khz, 100, 20000) * 1000;
  cap_ma = (uint32_t)pov::clampv((int)s.cap_ma, 50, 5000);
}

static BenchState defaults_state() {
  BenchState s;
  memset(&s, 0, sizeof(s));
  s.ver = STATE_VER; s.chain_sel = 0; s.n_leds = 14; s.gb = 4; s.val = 255; s.pattern = '0';
  s.spi_mode = 0; s.duty = 50; s.mosi_dly = 0; s.start_b = 4; s.end_b = 4 * (POV_LEDS_PER_CHAIN / 32 + 1); s.latch_b = 4;
  s.short_frame = 0; s.repeats = 1;
  s.raw4[0] = 0xE4; s.raw4[1] = 0x00; s.raw4[2] = 0x00; s.raw4[3] = 0xFF;
  s.spi_khz = 1000; s.cap_ma = 1000;
  return s;
}

static BenchState saved_state;                    // what NVS holds
static BenchState seen_state;                     // the last snapshot the loop looked at (auto-save debounce)
static uint32_t state_changed_ms = 0;

static void save_state(bool verbose) {
  BenchState s = snapshot_state();
  Preferences p;
  if (!p.begin("bench", false)) { out.println("NVS: open failed, state not saved"); return; }
  size_t w = p.putBytes("st", &s, sizeof(s));
  p.end();
  if (w != sizeof(s)) { out.println("NVS: write failed, state not saved"); return; }
  saved_state = s; seen_state = s;
  if (verbose) out.println("bench state saved to NVS");
}

static bool load_state() {
  Preferences p;
  if (!p.begin("bench", true)) return false;      // read-only open fails when the namespace doesn't exist yet
  BenchState s;
  bool ok = p.getBytesLength("st") == sizeof(s) && p.getBytes("st", &s, sizeof(s)) == sizeof(s) && s.ver == STATE_VER;
  p.end();
  if (ok) apply_state(s);
  return ok;
}

static void print_state(const char* what) {
  out.printf("%s: chain %s, %d LEDs, field %u, value %u, pattern %c, cap %u mA, SPI %d kHz mode %d duty %d %% d%d, z%d e%d l%d o%d r%d\n", what,
             chain_sel == 2 ? "both" : (chain_sel ? "1" : "0"), n_leds, (unsigned)gb, (unsigned)val, pattern, (unsigned)cap_ma, SPI_HZ / 1000,
             spi_mode, duty_pct, mosi_dly, start_b, end_b, latch_b, (int)short_frame, repeats);
}

// frame-resend bookkeeping (the 100 ms resend must keep going with Wi-Fi up; `i` and `q` report it)
static uint32_t rs_count = 0, rs_last_ms = 0, rs_gap_max = 0;

static void resend_report() {
  uint32_t nominal = (pattern == 'y' || pattern == 'Y' || pattern == 'U' || pattern == 'K') ? 10u : pattern == 'b' ? 40u : 100u;
  out.printf("frame resends: %u since boot, worst gap %u ms since the last report (nominal %u ms; commands, NVS saves and t/k "
             "block the loop, so look at it after a quiet spell)\n", (unsigned)rs_count, (unsigned)rs_gap_max, (unsigned)nominal);
  rs_gap_max = 0;
}

// ---------------------------------------------------------------- SPI (phase 0 keeps the result queue: blocking sends)
static esp_err_t add_device(int ch) {
  spi_device_interface_config_t cfg = {};
  cfg.clock_speed_hz = SPI_HZ; cfg.mode = (uint8_t)spi_mode; cfg.spics_io_num = -1; cfg.queue_size = 4;
  cfg.duty_cycle_pos = (uint16_t)(duty_pct * 256 / 100);   // 50 % -> 128, the driver's default
  return spi_bus_add_device(HOST[ch], &cfg, &dev[ch]);
}

// MOSI delay (ESP32 TRM, SPI_CTRL2_REG): mosi_delay_num delays DATA by N APB cycles (12.5 ns at 80 MHz);
// mosi_delay_mode delays it by half a clock period (mode 2 when ck_out_edge = 0, i.e. SPI modes 0 and 3; mode 1 in
// SPI modes 1 and 2). spi_bus_initialize clears the register; the driver's per-device and per-transaction set-up only
// rewrites the CS-timing and MISO fields (checked in libhal.a of IDF 5.5.5), so this holds until the next bus init.
static void apply_mosi_delay() {
  for (int ch = 0; ch < 2; ch++) {
    spi_dev_t* hw = HW[ch];
    if (mosi_dly >= 8) { hw->ctrl2.mosi_delay_mode = (spi_mode == 1 || spi_mode == 2) ? 1 : 2; hw->ctrl2.mosi_delay_num = 0; }
    else { hw->ctrl2.mosi_delay_mode = 0; hw->ctrl2.mosi_delay_num = (uint32_t)mosi_dly; }
  }
}

static void setup_spi(int ch, int mosi, int sck) {
  spi_bus_config_t bus = {};
  bus.mosi_io_num = mosi; bus.miso_io_num = -1; bus.sclk_io_num = sck;
  bus.quadwp_io_num = -1; bus.quadhd_io_num = -1; bus.max_transfer_sz = TX_BYTES;
  ESP_ERROR_CHECK(spi_bus_initialize(HOST[ch], &bus, SPI_DMA_CH_AUTO));
  ESP_ERROR_CHECK(add_device(ch));
}

// re-add both devices with the current clock / mode / duty (the buses stay up, so the MOSI delay is re-applied too)
static void reconfigure() {
  for (int ch = 0; ch < 2; ch++) {
    if (dev[ch]) { spi_bus_remove_device(dev[ch]); dev[ch] = nullptr; }
    esp_err_t e = add_device(ch);
    if (e != ESP_OK) out.printf("chain %d: spi_bus_add_device failed (%s); chain %d is off until the next change\n", ch, esp_err_to_name(e), ch);
  }
  apply_mosi_delay();
}

static void set_spi_clock(int hz) { SPI_HZ = hz; reconfigure(); }

// what goes on the wire for chain ch: start zeros, the LED slots, end-frame 0xFF bytes, latch zeros
static int assemble(int ch) {
  int nled = short_frame ? n_leds : (int)POV_LEDS_PER_CHAIN;
  uint8_t* p = tx[ch];
  memset(p, 0x00, start_b); p += start_b;
  memcpy(p, frame[ch] + 4, 4 * nled); p += 4 * nled;
  memset(p, 0xFF, end_b); p += end_b;
  memset(p, 0x00, latch_b); p += latch_b;
  tx_len[ch] = (int)(p - tx[ch]);
  return tx_len[ch];
}

static void send(int ch) {
  if (!dev[ch]) return;
  int len = assemble(ch);
  for (int i = 0; i < repeats; i++) {
    spi_transaction_t t = {};
    t.length = (size_t)len * 8;
    t.tx_buffer = tx[ch];
    if (spi_device_transmit(dev[ch], &t) != ESP_OK) spi_err++;   // blocking: queue + wait
  }
}

static void send_selected() {
  if (chain_sel == 0 || chain_sel == 2) send(0);
  if (chain_sel == 1 || chain_sel == 2) send(1);
}

static uint32_t wire_us(int bytes) {
  int khz = 0;
  if (dev[0]) spi_device_get_actual_freq(dev[0], &khz);
  if (khz <= 0) khz = SPI_HZ / 1000;
  return (uint32_t)((uint64_t)bytes * 8 * 1000 / (uint32_t)khz);
}

static void print_frame() {
  int ch = chain_sel == 1 ? 1 : 0;
  int len = assemble(ch);
  out.printf("frame: %d B start zeros, %d LED slots (%d lit), %d B end 0xFF, %d B latch zeros = %d B = %u us on the wire, sent x%d every 100 ms; SPI errors %u\n",
                start_b, short_frame ? n_leds : (int)POV_LEDS_PER_CHAIN, n_leds, end_b, latch_b, len, (unsigned)wire_us(len), repeats, (unsigned)spi_err);
}

// read the hardware back: proves the driver applied the clock, mode, duty and kept the MOSI delay
static void print_config() {
  for (int ch = 0; ch < 2; ch++) {
    if (!(chain_sel == 2 || chain_sel == ch)) continue;
    int khz = 0;
    if (dev[ch]) spi_device_get_actual_freq(dev[ch], &khz);
    spi_dev_t* hw = HW[ch];
    unsigned n = hw->clock.clk_equ_sysclk ? 1 : hw->clock.clkcnt_n + 1, h = hw->clock.clk_equ_sysclk ? 1 : hw->clock.clkcnt_h + 1;
    out.printf("chain %d: SPI asked %d kHz, actual %d kHz | mode %d (hw: CLK idles %s, out edge %u) | CLK high %u of %u counts (asked %d %%) | "
                  "MOSI delay mode %u num %u (asked d%d) | pins via %s\n",
                  ch, SPI_HZ / 1000, khz, spi_mode, hw->pin.ck_idle_edge ? "high" : "low", (unsigned)hw->user.ck_out_edge, h, n, duty_pct,
                  (unsigned)hw->ctrl2.mosi_delay_mode, (unsigned)hw->ctrl2.mosi_delay_num, mosi_dly,
                  spicommon_bus_using_iomux(HOST[ch]) ? "IO_MUX" : "GPIO matrix");
  }
  print_frame();
}

// ---------------------------------------------------------------- LED-space patterns
// LED k of a chain gets (r, g, b) at field g5; off = current field 0
static void set_led(uint8_t* buf, int k, uint8_t r, uint8_t g, uint8_t b, uint8_t g5) {
  uint8_t* p = buf + 4 + 4 * k;
  bool on = (r | g | b) != 0;
  p[0] = 0xE0 | (on ? (g5 & 31) : 0);
  p[1] = POV_GAMMA22[b]; p[2] = POV_GAMMA22[g]; p[3] = POV_GAMMA22[r];
}

// LED drive in mA for the current frame, each LED at its own field (model: 20 mA per channel at field 31, linear)
static uint32_t pattern_drive_ma(int ch) {
  uint32_t sum = 0;
  for (int k = 0; k < POV_LEDS_PER_CHAIN; k++) {
    const uint8_t* p = frame[ch] + 4 + 4 * k;
    sum += (uint32_t)(p[1] + p[2] + p[3]) * (p[0] & 31);
  }
  return sum * pov::I_CH_MA / (255u * 31u);
}

// breathing scale for Y and U: lo..1.00 on a 3 s sine from millis(), so it is independent of the slide
static float pulse(float lo) {
  float c = 0.5f - 0.5f * cosf(6.2831853f * (float)(millis() % 3000u) / 3000.0f);   // 0..1..0
  return lo + (1.0f - lo) * c;
}

static void build(int ch) {
  pov::build_blank(frame[ch]);
  uint8_t g5 = gb;
  if (pattern == '9') {                           // dense white at the cap: fit the field like the firmware does
    uint32_t drive = (uint32_t)n_leds * 60;        // 3 x 20 mA per LED at full duty, field 31
    g5 = pov::fit_gb(drive, 31, cap_ma, (uint32_t)n_leds * pov::I_DARK_MA);
  }
  for (int k = 0; k < n_leds && k < POV_LEDS_PER_CHAIN; k++) {
    switch (pattern) {
      case '1': set_led(frame[ch], k, val, 0, 0, g5); break;
      case '2': set_led(frame[ch], k, 0, val, 0, g5); break;
      case '3': set_led(frame[ch], k, 0, 0, val, g5); break;
      case '4': set_led(frame[ch], k, val, val, val, g5); break;
      case '9': set_led(frame[ch], k, 255, 255, 255, g5); break;
      case '5': if (k % 14 == k / 14) set_led(frame[ch], k, 255, 255, 255, g5); break;
      case '6': { uint8_t v = (uint8_t)(16 + POV_LED_ROW[ch][k] * 239 / (POV_ROWS - 1)); set_led(frame[ch], k, v, v, v, g5); break; }
      case '7': if (k == n_leds - 1) set_led(frame[ch], k, 255, 255, 255, g5); break;
      case '8': if (k == walk % n_leds) set_led(frame[ch], k, 255, 255, 255, g5); break;
      case 'y': case 'Y': {                         // every LED lit: a full rainbow across the strip sliding back and forth
        int ph = walk % 512, tri = ph < 256 ? ph : 511 - ph;   // 0..255..0
        uint8_t hue = (uint8_t)(tri + k * 255 / (n_leds > 0 ? n_leds : 1)), sec = hue / 43, f = (uint8_t)((hue % 43) * 6);
        uint8_t r = 0, gg = 0, bb = 0;
        switch (sec) { case 0: r = 255; gg = f; break; case 1: r = 255 - f; gg = 255; break; case 2: gg = 255; bb = f; break;
                       case 3: gg = 255 - f; bb = 255; break; case 4: r = f; bb = 255; break; default: r = 255; bb = 255 - f; }
        if (pattern == 'Y') {                       // breathe: 0.10..1.00 of the colour on a 3 s sine, from millis() (not walk)
          float s = pulse(0.10f);
          r = (uint8_t)(r * s + 0.5f); gg = (uint8_t)(gg * s + 0.5f); bb = (uint8_t)(bb * s + 0.5f);
        }
        set_led(frame[ch], k, r, gg, bb, g5);
        break; }
      case 'U': case 'K': {                         // patriotic bands sliding back and forth, breathing: U = red / white / blue,
                                                    // K = Canada, red / white / white / red (the flag's 1:2:1 bars, repeating)
        static const float CU[3][3] = { {255, 0, 0}, {166, 166, 166}, {0, 0, 255} };   // white at 65 % so the three read evenly
        static const float CK[4][3] = { {255, 0, 0}, {166, 166, 166}, {166, 166, 166}, {255, 0, 0} };
        const int NB = pattern == 'K' ? 4 : 3;
        const float (*C)[3] = pattern == 'K' ? CK : CU;
        const float period = (float)(n_leds > 2 ? n_leds : 3), w = period / (float)NB;   // one band period across the strip
        float ph = (float)(walk % 1024u) / 1024.0f;                                   // 2.56 s per pass (walk += 2 / 10 ms)
        float off = 0.5f * period * (1.0f - cosf(6.2831853f * ph));                   // eased bounce, 0..period..0
        float t = fmodf((float)k + off, period) / w;                                  // 0..NB in band units
        int i = (int)t; if (i > NB - 1) i = NB - 1;
        float f = t - (float)i, m = 0.0f;                                             // solid core, blend over the last 35 %
        if (f > 0.65f) { m = (f - 0.65f) / 0.35f; m = m * m * (3.0f - 2.0f * m); }   // smoothstep into the next band
        int j = (i + 1) % NB;
        float s = pulse(0.15f);
        float rf = (C[i][0] + (C[j][0] - C[i][0]) * m) * s, gf = (C[i][1] + (C[j][1] - C[i][1]) * m) * s,
              bf = (C[i][2] + (C[j][2] - C[i][2]) * m) * s;
        set_led(frame[ch], k, (uint8_t)(rf + 0.5f), (uint8_t)(gf + 0.5f), (uint8_t)(bf + 0.5f), g5);
        break; }
      case 'b': {                                   // rainbow comet bouncing end to end, 3-LED fading tail
        int span = n_leds > 1 ? 2 * (n_leds - 1) : 1, ph = walk % span;
        int head = ph < n_leds ? ph : span - ph, dir = ph < n_leds ? 1 : -1;
        int d = (head - k) * dir;                   // 0 at the head, 1..3 behind it
        if (d >= 0 && d <= 3) {
          uint8_t hue = (uint8_t)(walk * 6), sec = hue / 43, f = (uint8_t)((hue % 43) * 6);
          uint8_t r = 0, gg = 0, bb = 0;
          switch (sec) { case 0: r = 255; gg = f; break; case 1: r = 255 - f; gg = 255; break; case 2: gg = 255; bb = f; break;
                         case 3: gg = 255 - f; bb = 255; break; case 4: r = f; bb = 255; break; default: r = 255; bb = 255 - f; }
          uint8_t sc = (uint8_t)(255 >> (2 * d));
          set_led(frame[ch], k, (uint8_t)(r * sc / 255), (uint8_t)(gg * sc / 255), (uint8_t)(bb * sc / 255), g5);
        }
        break; }
      case 'a': set_led(frame[ch], k, val, 0, 0, (uint8_t)(1u << (k % 5))); break;
      case 'x': memcpy(frame[ch] + 4 + 4 * k, raw4, 4); break;
      default: break;
    }
  }
}

static void rebuild_and_send() {
  for (int ch = 0; ch < 2; ch++) build(ch);
  send_selected();
  if (pattern == '9') {
    uint32_t drive = (uint32_t)n_leds * 60;
    uint8_t g5 = pov::fit_gb(drive, 31, cap_ma, (uint32_t)n_leds * pov::I_DARK_MA);
    uint32_t pred = drive * g5 / 31 + (uint32_t)n_leds * pov::I_DARK_MA;
    out.printf("dense white: field %u -> predicted %u mA per chain (cap %u); measure it at the supply\n", (unsigned)g5, (unsigned)pred, (unsigned)cap_ma);
  } else {
    int chains = chain_sel == 2 ? 2 : 1;
    uint32_t drive = pattern_drive_ma(0);
    if (pattern == 'x')
      out.printf("pattern x %02X %02X %02X %02X (header field %u, B G R raw), chain %s, %d LEDs: predicted %u mA per chain + %u mA idle, x%d\n",
                    raw4[0], raw4[1], raw4[2], raw4[3], (unsigned)(raw4[0] & 31), chain_sel == 2 ? "both" : (chain_sel ? "1" : "0"), n_leds,
                    (unsigned)drive, (unsigned)n_leds, chains);
    else
      out.printf("pattern %c, chain %s, %d LEDs, field %u: predicted %u mA per chain + %u mA idle, x%d\n", pattern,
                    chain_sel == 2 ? "both" : (chain_sel ? "1" : "0"), n_leds, (unsigned)gb, (unsigned)drive, (unsigned)n_leds, chains);
  }
}

// ---------------------------------------------------------------- SPI frame-time measurement (bench step 5)
static void measure_frame_time() {
  int ch = chain_sel == 1 ? 1 : 0;
  if (!dev[ch]) { out.println("chain has no SPI device (see the last error)"); return; }
  build(ch);
  int len = assemble(ch);
  int64_t mn = 1 << 30, mx = 0, sum = 0;
  for (int i = 0; i < 200; i++) {
    int64_t t0 = esp_timer_get_time();
    send(ch);
    int64_t d = esp_timer_get_time() - t0;
    mn = std::min(mn, d); mx = std::max(mx, d); sum += d;
  }
  out.printf("blocking spi_device_transmit x%d, %d B: min %lld avg %lld max %lld us (wire time %u us per frame at %d kHz)\n",
                repeats, len, (long long)mn, (long long)(sum / 200), (long long)mx, (unsigned)wire_us(len), SPI_HZ / 1000);
  // DMA-queued: queue, then wait for the result; the gap between queue and done is the real transfer time
  mn = 1 << 30; mx = 0; sum = 0;
  spi_transaction_t t = {};
  t.length = (size_t)len * 8; t.tx_buffer = tx[ch];
  for (int i = 0; i < 200; i++) {
    int64_t t0 = esp_timer_get_time();
    spi_device_queue_trans(dev[ch], &t, portMAX_DELAY);
    int64_t t1 = esp_timer_get_time();
    spi_transaction_t* r;
    spi_device_get_trans_result(dev[ch], &r, portMAX_DELAY);
    int64_t d = esp_timer_get_time() - t1, q = t1 - t0;
    mn = std::min(mn, d); mx = std::max(mx, d); sum += d;
    if (i == 0) out.printf("queue_trans returned after %lld us (the task is free while DMA runs)\n", (long long)q);
  }
  out.printf("DMA queued: min %lld avg %lld max %lld us from queue to done\n", (long long)mn, (long long)(sum / 200), (long long)mx);
}

// ---------------------------------------------------------------- column clock (a frame every 2.78 ms for 10 s)
static gptimer_handle_t clk = nullptr;
static volatile uint32_t alarms = 0;
static volatile int64_t alarm_t = 0;

static bool IRAM_ATTR on_clk(gptimer_handle_t, const gptimer_alarm_event_data_t*, void*) {
  alarms = alarms + 1;
  alarm_t = esp_timer_get_time();
  return false;
}

static void column_clock_test() {
  if (!clk) {
    gptimer_config_t tc = {};
    tc.clk_src = GPTIMER_CLK_SRC_DEFAULT; tc.direction = GPTIMER_COUNT_UP; tc.resolution_hz = 1000000;
    ESP_ERROR_CHECK(gptimer_new_timer(&tc, &clk));
    gptimer_event_callbacks_t cbs = {}; cbs.on_alarm = on_clk;
    ESP_ERROR_CHECK(gptimer_register_event_callbacks(clk, &cbs, nullptr));
    ESP_ERROR_CHECK(gptimer_enable(clk));
  }
  gptimer_alarm_config_t al = {};
  al.alarm_count = COL_US; al.reload_count = 0; al.flags.auto_reload_on_alarm = true;
  ESP_ERROR_CHECK(gptimer_set_raw_count(clk, 0));
  ESP_ERROR_CHECK(gptimer_set_alarm_action(clk, &al));
  ESP_ERROR_CHECK(gptimer_start(clk));
  uint32_t handled = 0, missed = 0, sent = 0;
  int64_t worst = 0, t_end = esp_timer_get_time() + 10000000;
  out.printf("column clock: a frame every %u us for 10 s; the last LED cycles red/green/blue every frame\n", (unsigned)COL_US);
  while (esp_timer_get_time() < t_end) {
    uint32_t a = alarms;
    if (a == handled) continue;
    if (a - handled > 1) missed += a - handled - 1;
    handled = a;
    int64_t lat = esp_timer_get_time() - alarm_t;
    worst = std::max(worst, lat);
    last_led_phase = (uint8_t)((last_led_phase + 1) % 3);
    for (int ch = 0; ch < 2; ch++) {
      build(ch);
      int k = n_leds - 1;
      set_led(frame[ch], k, last_led_phase == 0 ? 255 : 0, last_led_phase == 1 ? 255 : 0, last_led_phase == 2 ? 255 : 0, gb);
    }
    send_selected();
    sent++;
  }
  gptimer_stop(clk);
  out.printf("sent %u frames, missed %u alarms, worst alarm-to-send latency %lld us (column is %u us)\n", (unsigned)sent, (unsigned)missed, (long long)worst, (unsigned)COL_US);
  out.println("expect: the last LED looked white-ish (all three colours at 360 fps); a single colour = the end frame did not latch it");
  rebuild_and_send();
}

// ---------------------------------------------------------------- hall readout (bench steps 8-9)
static pov::Hall hall;
static pov::SchedCfg sched_cfg;
static volatile int64_t fall_t = 0, rise_t = 0, width_us = 0;
static volatile uint32_t edges = 0;

static void IRAM_ATTR hall_change() {
  int64_t now = esp_timer_get_time();
  edges = edges + 1;
  if (digitalRead(PIN_HALL) == LOW) { fall_t = now; pov::hall_pulse(hall, sched_cfg, now); }
  else { rise_t = now; if (fall_t) width_us = now - fall_t; }
}

static void hall_report() {
  pov::HallSnap h = pov::snapshot(hall);
  out.printf("hall: pulses %u rejected %u resyncs %u | period %u us -> %.1f rpm (valid %d, agree %u) | width %lld us | edges %u | pin %d\n",
                (unsigned)h.pulses, (unsigned)h.rejected, (unsigned)h.resyncs, (unsigned)h.rev_us, h.rev_us ? 60e6 / h.rev_us : 0.0,
                (int)h.valid, (unsigned)h.agree, (long long)width_us, (unsigned)edges, digitalRead(PIN_HALL));
}

// ---------------------------------------------------------------- Wi-Fi + OTA + the TCP command port
// Non-blocking: wifi_begin() starts the join, wifi_poll() (every loop) notices the connection, starts mDNS / OTA / the
// TCP server once, and re-kicks the join every 20 s while it is down. Wi-Fi runs on core 0; the loop and its SPI sends
// stay on core 1 (the SPI clock is hardware, so Wi-Fi can only delay when a frame starts, never stretch one).
static const bool WIFI_CONFIGURED = strcmp(WIFI_SSID, "FILL_IN") != 0 && WIFI_SSID[0] != '\0';
static bool wifi_want = false, wifi_up = false, net_services = false;
static uint32_t wifi_try_ms = 0;

static bool wifi_begin() {
  if (!WIFI_CONFIGURED) { out.println("Wi-Fi off: src/wifi_secrets.h has no SSID (copy wifi_secrets.example.h, fill it in, rebuild)"); return false; }
  WiFi.setHostname("pov");                        // before mode(): the hostname is applied when the STA interface starts
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);                           // no modem sleep: snappy telnet and a steady supply current baseline
  WiFi.setAutoReconnect(true);
#ifdef POV_STATIC_IP                              // optional (wifi_secrets.h): a fixed address instead of DHCP
  WiFi.config(IPAddress(POV_STATIC_IP), IPAddress(POV_GATEWAY), IPAddress(POV_SUBNET), IPAddress(POV_DNS));
#endif
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  wifi_want = true; wifi_try_ms = millis();
  out.println("joining Wi-Fi (in the background)");
  return true;
}

static void on_wifi_join() {
  if (!net_services) {
    MDNS.begin("pov");
    ArduinoOTA.setHostname("pov");
    ArduinoOTA.setPassword(OTA_PASS);
    ArduinoOTA.setTimeout(povota::OTA_RX_TIMEOUT_MS);   // default 1 s x 3 tries: one lost packet aborted the update
    ArduinoOTA.onStart([]() { out.println("OTA start (LEDs off)"); povota::radio_for_ota(); for (int ch = 0; ch < 2; ch++) pov::build_blank(frame[ch]); send(0); send(1); });
    ArduinoOTA.begin();                           // also advertises _arduino._tcp (port 3232) on mDNS
    MDNS.addService("telnet", "tcp", 23);
    tcp_server.begin();
    tcp_server.setNoDelay(true);
    net_services = true;
    wifi_on = true;
  }
  String ip = WiFi.localIP().toString();
  out.printf("Wi-Fi up: ip %s, rssi %d dBm | commands: telnet pov.local 23  or  py tools/pov_cmd.py \"q\" (--host %s) | "
             "OTA: tools\\pio.cmd run -e phase0 -t upload --upload-port %s (add espota in platformio_local.ini)\n",
             ip.c_str(), WiFi.RSSI(), ip.c_str(), ip.c_str());
}

static void wifi_poll() {
  if (!wifi_want) return;
  bool c = WiFi.status() == WL_CONNECTED;
  if (c && !wifi_up) { wifi_up = true; on_wifi_join(); }
  else if (!c && wifi_up) { wifi_up = false; wifi_try_ms = millis(); out.println("Wi-Fi lost; rejoining in the background"); }
  else if (!c && millis() - wifi_try_ms > 20000) { wifi_try_ms = millis(); WiFi.disconnect(); WiFi.begin(WIFI_SSID, WIFI_PASS); }
}

// `w`: start the join if it isn't running and wait up to 10 s for it (the old blocking behaviour), then report
static void wifi_start() {
  if (wifi_up) { out.printf("Wi-Fi already up: ip %s, rssi %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI()); return; }
  if (!wifi_want && !wifi_begin()) return;
  out.print("waiting for Wi-Fi");
  for (int i = 0; i < 100 && WiFi.status() != WL_CONNECTED; i++) { delay(100); if (i % 10 == 0) out.print("."); }
  out.println();
  wifi_poll();
  if (!wifi_up) out.println("no Wi-Fi yet (check src/wifi_secrets.h and the AP); still retrying in the background");
}

static void wifi_report() {
  if (!WIFI_CONFIGURED) { out.println("Wi-Fi: not configured (placeholder src/wifi_secrets.h)"); return; }
  if (wifi_up)
    out.printf("Wi-Fi: up, ip %s, rssi %d dBm, TCP client %s\n", WiFi.localIP().toString().c_str(), WiFi.RSSI(),
               tcp.connected() ? tcp.remoteIP().toString().c_str() : "none");
  else out.printf("Wi-Fi: %s\n", wifi_want ? "joining" : "off (w to join)");
}

static void info() {
  out.printf("chip %s rev %d, %u MHz, flash %u MB, sdk %s, arduino %d.%d.%d\n", ESP.getChipModel(), ESP.getChipRevision(),
                (unsigned)ESP.getCpuFreqMHz(), (unsigned)(ESP.getFlashChipSize() >> 20), ESP.getSdkVersion(), ESP_ARDUINO_VERSION_MAJOR,
                ESP_ARDUINO_VERSION_MINOR, ESP_ARDUINO_VERSION_PATCH);
  out.printf("free heap %u (min %u), PSRAM %u (expect 0 on the WROOM-32)\n", (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getMinFreeHeap(), (unsigned)ESP.getPsramSize());
  out.printf("pins: chain 0 DATA %d CLK %d (VSPI/SPI3, %s), chain 1 DATA %d CLK %d (HSPI/SPI2, %s), hall %d; %d B frames, %u us at %d kHz\n",
                PIN_D0, PIN_C0, spicommon_bus_using_iomux(SPI3_HOST) ? "IO_MUX" : "GPIO matrix", PIN_D1, PIN_C1,
                spicommon_bus_using_iomux(SPI2_HOST) ? "IO_MUX" : "GPIO matrix", PIN_HALL, POV_FRAME_BYTES, (unsigned)wire_us(POV_FRAME_BYTES), SPI_HZ / 1000);
  out.printf("firmware %s, elf %s, ota image %s\n", POV_FW_VERSION, povota::elf_sha().c_str(), povota::state_name());
  wifi_report();
  resend_report();
}

static void help() {
  out.println("POV phase-0 bench sketch " POV_FW_VERSION ". USB/bank rule: pigtail unplugged while USB is in; never both without D1.");
  out.println("c0 c1 cb | nNN leds | gNN field | vNNN value | mNNNN cap mA | 0 off 1 R 2 G 3 B 4 W 5 strip# 6 rowramp 7 last 8 walk 9 dense | y rainbow Y rainbow+pulse U red-white-blue K red-white (Canada)");
  out.println("a field ladder (1 2 4 8 16) | xHHHHHHHH raw LED bytes hdr B G R (xE40000FF) | q show SPI set-up + frame");
  out.println("sNNNN kHz | pN SPI mode 0-3 | uNN CLK high % | dN DATA delay 0-7 x 12.5 ns, d8 half period | zN eN lN start/end/latch bytes | o0/o1 all/lit slots | rN send xN");
  out.println("t frame time | k column clock 10 s | h hall readout | w wifi+ota | i info | S save state | R defaults | ? help");
  out.println("several commands per line, space-separated (cb s8000 a); same commands on TCP 23 (telnet pov.local 23, tools/pov_cmd.py)");
}

// ---------------------------------------------------------------- one command handler for Serial and TCP
static void handle_cmd(const String& tok) {
  char k = tok[0];
  int v = tok.substring(1).toInt();
  switch (k) {
    case 'c': chain_sel = tok[1] == 'b' ? 2 : (tok[1] == '1' ? 1 : 0); rebuild_and_send(); break;
    case 'n': n_leds = pov::clampv(v, 1, (int)POV_LEDS_PER_CHAIN); rebuild_and_send(); break;
    case 'g': gb = (uint8_t)pov::clampv(v, 1, 31); rebuild_and_send(); break;
    case 's': set_spi_clock(pov::clampv(v, 100, 20000) * 1000); rebuild_and_send(); print_config(); break;
    case 'v': val = (uint8_t)pov::clampv(v, 0, 255); out.printf("colour value %u\n", (unsigned)val); rebuild_and_send(); break;
    case 'm': cap_ma = (uint32_t)pov::clampv(v, 50, 5000); rebuild_and_send(); break;
    case '0': case '1': case '2': case '3': case '4': case '5': case '6': case '7': case '8': case '9': case 'a': case 'b': case 'y': case 'Y': case 'U': case 'K':
      pattern = k; walk = 0; rebuild_and_send(); break;
    case 'x': {
      String hex = tok.substring(1);
      hex.trim();
      char* end = nullptr;
      uint32_t w = (uint32_t)strtoul(hex.c_str(), &end, 16);
      if (hex.length() != 8 || (end && *end)) { out.println("x needs 8 hex digits: header B G R, e.g. xE40000FF (red, field 4)"); break; }
      raw4[0] = (uint8_t)(w >> 24); raw4[1] = (uint8_t)(w >> 16); raw4[2] = (uint8_t)(w >> 8); raw4[3] = (uint8_t)w;
      pattern = 'x'; walk = 0; rebuild_and_send(); break;
    }
    case 'p': spi_mode = pov::clampv(v, 0, 3); reconfigure(); rebuild_and_send(); print_config(); break;
    case 'u': duty_pct = pov::clampv(v, 10, 90); reconfigure(); rebuild_and_send(); print_config(); break;
    case 'd': mosi_dly = pov::clampv(v, 0, 8); apply_mosi_delay(); rebuild_and_send(); print_config(); break;
    case 'z': start_b = pov::clampv(v, 0, 16); rebuild_and_send(); print_frame(); break;
    case 'e': end_b = pov::clampv(v, 0, 32); rebuild_and_send(); print_frame(); break;
    case 'l': latch_b = pov::clampv(v, 0, 8); rebuild_and_send(); print_frame(); break;
    case 'o': short_frame = v != 0; rebuild_and_send(); print_frame(); break;
    case 'r': repeats = pov::clampv(v, 1, 3); rebuild_and_send(); print_frame(); break;
    case 'q': print_config(); resend_report(); break;
    case 't': measure_frame_time(); break;
    case 'k': column_clock_test(); break;
    case 'h':
      hall_on = !hall_on;
      if (hall_on) { hall = pov::Hall(); attachInterrupt(digitalPinToInterrupt(PIN_HALL), hall_change, CHANGE); out.println("hall readout on (2 Hz)"); }
      else { detachInterrupt(digitalPinToInterrupt(PIN_HALL)); out.println("hall readout off"); }
      break;
    case 'w': wifi_start(); break;
    case 'i': info(); break;
    case 'S': save_state(true); print_state("saved"); break;
    case 'R':
      apply_state(defaults_state());
      walk = 0; reconfigure(); rebuild_and_send(); save_state(false); print_state("defaults restored and saved");
      break;
    default: help(); break;
  }
}

// a line may hold several commands separated by spaces, commas or semicolons ("cb s8000 a")
static void handle_line(const String& line) {
  int i = 0, n = (int)line.length();
  while (i < n) {
    while (i < n && strchr(" \t,;", line[i])) i++;
    int j = i;
    while (j < n && !strchr(" \t,;", line[j])) j++;
    if (j > i) handle_cmd(line.substring(i, j));
    i = j;
  }
}

// TCP port 23: one client; a new connection replaces the old one (a session that died with the Wi-Fi never blocks
// the port). Telnet option negotiation (IAC 255 ...) is skipped, CR is dropped, LF ends a line.
static void tcp_poll() {
  if (!net_services) return;
  if (tcp_server.hasClient()) {
    WiFiClient nc = tcp_server.accept();
    if (tcp.connected()) { tcp.print("another client connected; closing this session\r\n"); tcp.stop(); }
    tcp = nc;
    tcp.setNoDelay(true);
    Serial.printf("[tcp] client %s connected\n", tcp.remoteIP().toString().c_str());
    tcp.print("POV phase-0 " POV_FW_VERSION " command port; ? for help\r\n");
    print_state("state");
    tcp.print("pov> ");
  }
  static String tline;
  static int iac = 0;                               // 0 normal, 1 after IAC, 2 skip one option byte
  while (tcp.connected() && tcp.available()) {
    int c = tcp.read();
    if (c < 0) break;
    if (iac == 1) { iac = (c >= 251 && c <= 254) ? 2 : 0; continue; }
    if (iac == 2) { iac = 0; continue; }
    if (c == 255) { iac = 1; continue; }
    if (c == '\r' || c == 0) continue;
    if (c != '\n') { if (tline.length() < 200) tline += (char)c; continue; }
    tline.trim();
    if (tline.length()) { Serial.printf("[tcp] %s\n", tline.c_str()); handle_line(tline); }
    tline = "";
    if (tcp.connected()) tcp.print("pov> ");      // the prompt tells tools/pov_cmd.py the replies are complete
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  bool restored = load_state();                     // before the SPI set-up: clock, mode and duty come from NVS
  saved_state = restored ? snapshot_state() : defaults_state();
  seen_state = snapshot_state();
  setup_spi(0, PIN_D0, PIN_C0);
  setup_spi(1, PIN_D1, PIN_C1);
  apply_mosi_delay();
  for (int ch = 0; ch < 2; ch++) { pov::build_blank(frame[ch]); send(ch); }
  pinMode(PIN_HALL, INPUT_PULLUP);
  help();
  info();
  print_state(restored ? "state restored from NVS" : "state (defaults, nothing saved yet)");
  if (restored && pattern != '0') rebuild_and_send();   // a power cycle comes back lit in the same test set-up
  if (WIFI_CONFIGURED) wifi_begin();
  else out.println("Wi-Fi auto-join off: placeholder src/wifi_secrets.h");
}

void loop() {
  static String line;
  static uint32_t last_walk = 0, last_hall = 0;
  if (wifi_on) ArduinoOTA.handle();
  povota::guard_poll(wifi_up);                    // confirm or roll back a fresh OTA image
  wifi_poll();
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { line += c; continue; }
    line.trim();
    if (line.length()) handle_line(line);
    line = "";
  }
  tcp_poll();
  // resend the current frame every 100 ms for every pattern (bench: a strip that missed a frame catches the next one,
  // and the scope always has bursts to trigger on); the walk also advances
  if (millis() - last_walk > ((pattern == 'y' || pattern == 'Y' || pattern == 'U' || pattern == 'K') ? 10u : pattern == 'b' ? 40u : 100u)) {
    uint32_t now = millis();
    if (rs_last_ms) rs_gap_max = std::max(rs_gap_max, now - rs_last_ms);
    rs_last_ms = now; rs_count++;
    last_walk = now;
    if (pattern == '8' || pattern == 'b') walk++;
    if (pattern == 'y' || pattern == 'Y' || pattern == 'U' || pattern == 'K') walk += 2;
    for (int ch = 0; ch < 2; ch++) build(ch);
    send_selected();
  }
  if (hall_on && millis() - last_hall > 500) { last_hall = millis(); hall_report(); }
  // auto-save: once the state has been unchanged for 2 s and differs from NVS, write it (one flash write per burst of
  // commands, not one per command)
  BenchState s = snapshot_state();
  if (memcmp(&s, &seen_state, sizeof(s)) != 0) { seen_state = s; state_changed_ms = millis(); }
  else if (memcmp(&s, &saved_state, sizeof(s)) != 0 && millis() - state_changed_ms > 2000) save_state(false);
  delay(2);
}
