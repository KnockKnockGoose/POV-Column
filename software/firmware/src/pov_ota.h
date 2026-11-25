// pov_ota.h - OTA hardening shared by the image firmware (src/main.cpp) and the bench sketch (src/phase0/phase0.cpp).
// Include it from exactly ONE .cpp per firmware: it defines verifyRollbackLater().
// Why each piece exists: docs/2026-11-13-ota-failure-review.md (OTA failure review, 2026-11-13).
//
//  1. Rollback guard. The bootloader (CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y in arduino-esp32 3.3.x) boots a freshly
//     OTA'd image as "pending verify". Arduino normally marks it valid at once; here it is marked valid only after Wi-Fi
//     has been up and the loop has run for CONFIRM_AFTER_MS. An image that crashes, boot-loops (the IDF 5.5 SPI bug of
//     2026-11-13) or never gets Wi-Fi is rolled back to the previous image instead of needing USB.
//     USB-flashed images have no OTA state and are not affected.
//  2. ArduinoOTA receive timeout. The library waits 1 s for data, re-sends its byte count 3 times and aborts: about 4 s
//     of silence kills the transfer, while the board's own TCP retransmit timeout starts at 3 s (CONFIG_LWIP_TCP_RTO_TIME)
//     and doubles. One doubled retransmit on a lossy link (5 % ping loss measured in the sled) ended every OTA silently.
//  3. Full TX power while flashing. The image firmware joins at 13 dBm (bank-power current spikes); the LEDs are dark
//     during an update, so the radio gets its full 19.5 dBm back for the transfer.
//  4. Build id. elf_sha() is the first 16 hex digits of the app ELF SHA-256 that the build writes into the image
//     (esp_app_desc_t); tools/ota_flash.py reads the same field from firmware.bin and checks that the board really runs
//     the new build after the update.
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <esp_ota_ops.h>
#include <esp_app_desc.h>

// Arduino calls this (weak, C linkage) from initArduino(): true = "the sketch confirms the image itself".
extern "C" bool verifyRollbackLater() { return true; }

namespace povota {

static const uint32_t OTA_RX_TIMEOUT_MS = 8000;    // ArduinoOTA per-wait timeout (default 1000); 4 waits = 32 s of slack
static const uint32_t CONFIRM_AFTER_MS = 15000;    // healthy this long after boot -> image confirmed
static const uint32_t ROLLBACK_AFTER_MS = 120000;  // still not healthy -> roll back to the previous image

inline bool pending_verify() {
  esp_ota_img_states_t s;
  return esp_ota_get_state_partition(esp_ota_get_running_partition(), &s) == ESP_OK && s == ESP_OTA_IMG_PENDING_VERIFY;
}

// "pending" (new OTA image, not yet confirmed), "valid" (confirmed OTA image), "usb" (flashed over USB: no OTA state)
inline const char* state_name() {
  esp_ota_img_states_t s;
  if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &s) != ESP_OK) return "usb";
  switch (s) {
    case ESP_OTA_IMG_PENDING_VERIFY: return "pending";
    case ESP_OTA_IMG_VALID: return "valid";
    case ESP_OTA_IMG_NEW: return "new";
    default: return "other";
  }
}

// Call every loop pass. healthy = the firmware can be reached again (Wi-Fi joined).
inline void guard_poll(bool healthy) {
  static int8_t st = -1;                           // -1 not checked yet, 1 pending, 0 nothing to do
  if (st == 0) return;
  if (st < 0) {
    st = pending_verify() ? 1 : 0;
    if (st) Serial.println("OTA image pending verify: confirms after 15 s with Wi-Fi, else rolls back at 120 s");
    return;
  }
  uint32_t ms = millis();
  if (healthy && ms > CONFIRM_AFTER_MS) {
    esp_ota_mark_app_valid_cancel_rollback();
    Serial.println("OTA image confirmed");
    st = 0;
  } else if (ms > ROLLBACK_AFTER_MS) {
    Serial.println("OTA image never got healthy: rolling back to the previous image");
    Serial.flush();
    esp_ota_mark_app_invalid_rollback_and_reboot();
  }
}

inline String elf_sha() {
  const esp_app_desc_t* d = esp_app_get_description();
  char s[17];
  for (int i = 0; i < 8; i++) snprintf(s + 2 * i, 3, "%02x", d->app_elf_sha256[i]);
  return String(s);
}

inline void radio_for_ota() {
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
}

}  // namespace povota
