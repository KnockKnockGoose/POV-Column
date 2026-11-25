// cap_audit_host.cpp - QA harness for the check-pack-send audit (docs/2026-11-23-check-pack-send-audit.md).
//
// Runs the column firmware's OWN check code on the PC, on .pova files the pipeline produced, so a worst-case animation
// can be pushed through the firmware's checks without the board:
//   1. the upload check: pova_check_begin/feed/end (lib/povcore/pova.h), fed in 1,436-byte pieces the way
//      on_upload_chunk receives a multipart upload (any piece size gives the same answer; that is the point of it);
//   2. the name check: a verbatim copy of main.cpp valid_name() (main.cpp is ESP32-only and cannot be built here);
//   3. the load-time current cap: the body of main.cpp do_load() from the size test to fit_gb(), calling the same
//      povframe.h / pova.h functions (pova_parse with the CRC, pova_decode, the palette-index test, worst_column_ma
//      at gb 31, fit_gb at the requested brightness).
// One JSON line per file on stdout. Build and run (MinGW g++ 5.1 from PlatformIO, the native env's compiler):
//
//   set PATH=C:\pio\packages\toolchain-gccmingw32\bin;%PATH%
//   g++ -std=gnu++14 -O2 -Wall -mfpmath=sse -msse2 -static -static-libgcc -static-libstdc++ -I lib/povcore ^
//       -o %TEMP%\cap_audit_host.exe tools/cap_audit_host.cpp
//   %TEMP%\cap_audit_host.exe file1.pova[=upload_name] file2.pova ...
//
// software/tests/checkpack_audit.py builds it and drives it.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <vector>
#include <string>
#include "povframe.h"
#include "pova.h"

// ---- verbatim copy of main.cpp valid_name() (2026-11-23, main.cpp:392-400) ----
static bool valid_name(const char* name) {
  size_t n = name ? strlen(name) : 0;
  if (n == 0 || n > 28) return false;
  for (size_t i = 0; i < n; i++) {
    char c = name[i];
    if (!(isalnum((unsigned char)c) || c == '_' || c == '-' || c == '.')) return false;
  }
  return name[0] != '.';
}

static std::string jstr(const char* s) {
  std::string o = "\"";
  for (; s && *s; s++) {
    if (*s == '"' || *s == '\\') o += '\\';
    o += *s;
  }
  return o + "\"";
}

int main(int argc, char** argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: cap_audit_host file.pova[=upload_name] ...\n");
    return 2;
  }
  static PovaAnim anim;                         // big (frame tables): keep it off the stack
  static uint8_t frame[POV_FRAME_PIXELS];
  const uint8_t GB_REQ[] = {31, 23, 12, 4};     // settings.gb values to report: full, the 75 % rule, 11-22's 12, 4
  for (int ai = 1; ai < argc; ai++) {
    std::string arg = argv[ai], path = arg, name;
    size_t eq = arg.rfind('=');
    if (eq != std::string::npos && eq > 2) { path = arg.substr(0, eq); name = arg.substr(eq + 1); }
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) { printf("{\"file\":%s,\"error\":\"cannot open\"}\n", jstr(path.c_str()).c_str()); continue; }
    std::vector<uint8_t> buf;
    uint8_t tmp[4096];
    size_t k;
    while ((k = fread(tmp, 1, sizeof tmp, f)) > 0) buf.insert(buf.end(), tmp, tmp + k);
    fclose(f);
    size_t n = buf.size();

    // 1. upload check, as on_upload_chunk does it: first the request's Content-Length (file + ~200 B of multipart
    //    framing from Python requests) against 65,536 + 2,048 -> 413; then the streamed check. Note: pova_check_feed
    //    refuses the piece that would pass 65,536 B WITHOUT adding it to chk.total, so on_upload_chunk's
    //    `chk.total > POVA_MAX_FILE ? UP_BIG : UP_BAD` picks UP_BAD: a file of 65,537-67,384 B gets 400 "bad file: too
    //    big", not 413. Mirrored here as the board does it.
    PovaCheck chk;
    pova_check_begin(chk);
    bool up_ok = true;
    int http = 200;
    const char* up_err = "";
    if (n + 200 > POVA_MAX_FILE + 2048) { up_ok = false; http = 413; up_err = "too big (max 65536 B)"; }
    for (size_t p = 0; p < n && up_ok; p += 1436) up_ok = pova_check_feed(chk, buf.data() + p, std::min((size_t)1436, n - p));
    if (up_ok) up_ok = pova_check_end(chk);
    if (!up_ok && http == 200) { http = chk.total > POVA_MAX_FILE ? 413 : 400; up_err = chk.err ? chk.err : "invalid"; }

    // 2. name (only when one was given: the upload name pov_request.py would send)
    std::string name_json = "null";
    if (!name.empty()) name_json = valid_name(name.c_str()) ? "true" : "false";

    printf("{\"file\":%s,\"bytes\":%u,\"upload_http\":%d,\"upload_err\":%s,\"name\":%s,\"name_ok\":%s",
           jstr(path.c_str()).c_str(), (unsigned)n, http, jstr(up_err).c_str(), jstr(name.c_str()).c_str(),
           name_json.c_str());

    // 3. do_load(): size, parse (CRC), per-frame decode + index check, worst rotor position at gb 31, fit_gb
    const char* load_err = "";
    uint32_t worst = 0;
    if (n < 24 || n > POVA_MAX_FILE) load_err = "bad size";
    else if (!pova_parse(anim, buf.data(), n, true) || anim.nframes == 0) load_err = "damaged file (CRC or structure)";
    else {
      uint16_t duty[POV_MAX_PAL];
      pov::palette_duty(anim.pal_rgb, anim.npal, duty);
      for (uint16_t i = 0; i < anim.nframes; i++) {
        bool ok = pova_decode(anim, i, frame);
        for (int p = 0; ok && p < POV_FRAME_PIXELS; p++) ok = frame[p] < anim.npal;
        if (!ok) { load_err = "bad frame data"; break; }
        worst = std::max(worst, pov::worst_column_ma(frame, duty, 31));
      }
    }
    printf(",\"load_err\":%s", jstr(load_err).c_str());
    if (!*load_err) {
      printf(",\"frames\":%u,\"npal\":%u,\"drive_ma_gb31\":%u,\"total_ma_gb31\":%u,\"cap_ma\":%u,\"fit\":{",
             (unsigned)anim.nframes, (unsigned)anim.npal, (unsigned)worst,
             (unsigned)(worst + pov::IDLE_MA + pov::I_ESP_MA), (unsigned)pov::CAP_MA);
      for (size_t g = 0; g < sizeof GB_REQ; g++) {
        uint8_t gb = pov::fit_gb(worst, GB_REQ[g], pov::CAP_MA);
        uint32_t drive = (uint32_t)((uint64_t)worst * gb / 31);
        printf("%s\"%u\":{\"gb_used\":%u,\"drive_ma\":%u,\"leds_ma\":%u,\"total_ma\":%u}", g ? "," : "", (unsigned)GB_REQ[g],
               (unsigned)gb, (unsigned)drive, (unsigned)(drive + pov::IDLE_MA), (unsigned)(drive + pov::IDLE_MA + pov::I_ESP_MA));
      }
      printf("}");
    }
    printf("}\n");
  }
  return 0;
}
