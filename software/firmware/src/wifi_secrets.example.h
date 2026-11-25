// Copy to src/wifi_secrets.h (gitignored) and fill in. main.cpp and phase0.cpp include it when present.
#pragma once
#define WIFI_SSID "FILL_IN"
#define WIFI_PASS "FILL_IN"
#define OTA_PASS "FILL_IN"       // ArduinoOTA password; the same string goes into platformio_local.ini (--auth=)
#define POV_TOKEN ""             // X-POV-Token for mutating API calls and the WebSocket; "" = no check (bench)

// Optional: a fixed address instead of DHCP. Leave these out and the board takes an address from your router
// and answers as pov.local. Four numbers separated by commas (they go straight into IPAddress(...)).
// #define POV_STATIC_IP 192,168,1,50
// #define POV_GATEWAY   192,168,1,1
// #define POV_SUBNET    255,255,255,0
// #define POV_DNS       192,168,1,1
