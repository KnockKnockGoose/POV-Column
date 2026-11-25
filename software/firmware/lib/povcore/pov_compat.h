// pov_compat.h - the few platform shims the povcore headers need, so the same code compiles for the ESP32 (Arduino core
// 3.x, xtensa g++ 14) and for the host unit tests (PlatformIO "native" env, MinGW g++ 5.1, -std=gnu++14).
// Rules for lib/povcore: C++14 only (the host compiler), no FreeRTOS, no Arduino types, no floating-point in ISR paths.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <algorithm>

#if defined(ARDUINO)
#include <Arduino.h>
#else
#include <stdio.h>
#include <stdlib.h>
#ifndef IRAM_ATTR
#define IRAM_ATTR
#endif
#ifndef DMA_ATTR
#define DMA_ATTR
#endif
#endif

namespace pov {

template <class T>
static inline T clampv(T v, T lo, T hi) { return v < lo ? lo : (v > hi ? hi : v); }

// strlcpy is not in MinGW's libc; newlib has it, but a private copy keeps both builds identical
static inline size_t strlcpy_(char* dst, const char* src, size_t n) {
  size_t len = strlen(src);
  if (n) {
    size_t c = len < n - 1 ? len : n - 1;
    memcpy(dst, src, c);
    dst[c] = 0;
  }
  return len;
}

// memmem is a GNU extension (newlib has it, MinGW does not)
static inline const uint8_t* memmem_(const uint8_t* hay, size_t hn, const char* needle, size_t nn) {
  if (nn == 0 || hn < nn) return nullptr;
  for (size_t i = 0; i + nn <= hn; i++)
    if (hay[i] == (uint8_t)needle[0] && memcmp(hay + i, needle, nn) == 0) return hay + i;
  return nullptr;
}

}  // namespace pov
