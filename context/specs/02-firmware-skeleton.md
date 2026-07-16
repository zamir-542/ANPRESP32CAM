# Unit 02: Firmware Skeleton — WiFi Join + BOOT-Triggered Upload (placeholder payload)

## Goal

An Arduino sketch that proves the board flashes, brings up its own Wi-Fi
access point (SoftAP) that the phone joins, and the full ESP32→phone HTTP
upload contract works end-to-end — all before the camera is involved. Using
SoftAP means no router, SIM, or internet is needed (the phone had no SIM for a
hotspot, and shared networks block device-to-device). On a BOOT-button press, a small hardcoded dummy JPEG buffer is
POSTed to the phone's `/upload`; the server's `200 {ok, plate, confidence}`
response is logged over serial. The status LED on GPIO 33 blinks to confirm
success or error. **No camera, no real image capture in this unit.**

Establishes three invariants from day one:

- **#1** — all GPIO numbers live in `firmware/pins.h`, nowhere else.
- **#2** — the ISR only sets a `volatile` flag; all real work happens in `loop()`.
- **#3** — secrets (AP SSID/password, phone IP) live only in untracked
  `firmware/secrets.h`; a committed `secrets.h.example` carries placeholders.

## Design / Contract

Firmware side of the HTTP contract defined in `interface-context.md`:

- `POST /upload` with `multipart/form-data`, field **`image`**, containing a
  hardcoded `DUMMY_JPEG[]` byte array (a minimal valid 1×1 JPEG — small enough
  to be declared inline). This is the **only** change from Unit 03: the real
  framebuffer replaces `DUMMY_JPEG`.
- Parse the JSON response for `ok` and `plate` (or `reason`) and print them.
- Log every upload attempt and outcome over serial at 115200 (phase-prefixed).
- Blink GPIO 33 (active-low status LED): 1 short blink on success (`ok:true`),
  2 rapid blinks on any failure (HTTP error or `ok:false`).

## File Layout

```
firmware/
  platescope/          <- Arduino sketch folder (matches .ino filename)
    platescope.ino     <- main sketch: setup(), loop()
    pins.h             <- single source of GPIO truth (invariant #1)
    secrets.h          <- gitignored; real SSID/password/IP go here
    secrets.h.example  <- committed; placeholder values
  README.md            <- pinned versions + flashing steps
```

## Implementation

### `firmware/platescope/pins.h`

All GPIO numbers and hardware constants. No other file may contain a raw pin
number or a magic hardware constant.

```cpp
#pragma once
#include <cstdint>

// -- BOOT button ------------------------------------------------------------
// GPIO 0 is the BOOT strap -- only read it as a button after boot, in loop().
constexpr uint8_t BOOT_BTN_PIN = 0;

// -- Status LED -------------------------------------------------------------
// On-board red LED on GPIO 33.  Active LOW.
constexpr uint8_t STATUS_LED_PIN  = 33;
constexpr uint8_t LED_ON          = LOW;
constexpr uint8_t LED_OFF         = HIGH;

// -- Flash LED (reserved for Unit 03) ---------------------------------------
constexpr uint8_t FLASH_LED_PIN   = 4;   // Active HIGH; keep off in this unit.

// -- Timing -----------------------------------------------------------------
constexpr uint32_t DEBOUNCE_MS    = 300;
constexpr uint32_t BLINK_SHORT_MS = 150;
constexpr uint32_t BLINK_GAP_MS   =  80;

// -- Serial -----------------------------------------------------------------
constexpr uint32_t SERIAL_BAUD    = 115200;

// -- Upload -----------------------------------------------------------------
constexpr uint16_t UPLOAD_PORT    = 8000;
constexpr char     UPLOAD_PATH[]  = "/upload";
```

### `firmware/platescope/secrets.h.example`

```cpp
#pragma once

// Copy this file to secrets.h and fill in your values.
// secrets.h is gitignored -- never commit it.
// SoftAP: the ESP32 CREATES this network; the phone joins it.

#define AP_SSID      "PlateScope-AP"    // Wi-Fi name the ESP32 broadcasts
#define AP_PASSWORD  "platescope123"    // min 8 chars (WPA2); change this
#define SERVER_IP    "192.168.4.2"      // phone's IP on the AP (gateway is .1)
```

### `firmware/platescope/secrets.h` (gitignored)

Created locally from `secrets.h.example` with the real values. Never committed.

### `firmware/platescope/platescope.ino`

#### Includes and globals

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include "pins.h"
#include "secrets.h"
```

- `volatile bool g_upload_requested = false;` -- the ISR's only output.
- `static uint32_t g_last_accepted_ms = 0;` -- debounce timestamp.
- A small `static const uint8_t DUMMY_JPEG[]` array: a hardcoded minimal valid
  JPEG (1x1 pixel, ~200 bytes). Declare `DUMMY_JPEG_LEN` alongside it.
  This is intentionally tiny -- it validates the wire contract, not image quality.

#### `setup()`

1. `Serial.begin(SERIAL_BAUD)`.
2. `pinMode(STATUS_LED_PIN, OUTPUT); digitalWrite(STATUS_LED_PIN, LED_OFF);`
3. `pinMode(FLASH_LED_PIN, OUTPUT); digitalWrite(FLASH_LED_PIN, LOW);`
   (ensure flash LED stays off for this unit)
4. `pinMode(BOOT_BTN_PIN, INPUT_PULLUP);`
5. `attachInterrupt(digitalPinToInterrupt(BOOT_BTN_PIN), onBootBtn, FALLING);`
6. Start SoftAP: `WiFi.mode(WIFI_AP); WiFi.softAP(AP_SSID, AP_PASSWORD);` + log
   the SSID and `WiFi.softAPIP()` (192.168.4.1), or `[ERR] AP start failed`.
   The upload guard uses `WiFi.softAPgetStationNum()` (phone connected?).
7. Print startup banner.

#### ISR `IRAM_ATTR void onBootBtn()`

```cpp
void IRAM_ATTR onBootBtn() { g_upload_requested = true; }
```

Nothing else -- no Serial, no delay, no LED writes (invariant #2).

#### `loop()`

```
if (!g_upload_requested) return;
g_upload_requested = false;

// Debounce
const uint32_t now = millis();
if ((now - g_last_accepted_ms) < DEBOUNCE_MS) {
  Serial.println("[DBG] bounce ignored");
  return;
}
g_last_accepted_ms = now;

// Post the dummy payload
doUpload();

// Drop any bounce that fired during the upload
g_upload_requested = false;
```

#### `doUpload()`

Build the multipart body in a heap buffer (body < 1 KB with DUMMY_JPEG), POST
it with `http.POST(buf, len)`, log the response, blink accordingly, free buffer.

Multipart structure:
```
--PlateScopeBoundary\r\n
Content-Disposition: form-data; name="image"; filename="cap.jpg"\r\n
Content-Type: image/jpeg\r\n
\r\n
<DUMMY_JPEG bytes>
\r\n--PlateScopeBoundary--\r\n
```

- HTTP 200 + response body => log `[HTTP] 200 <body>` => `blinkOk()`
- Any other code => log `[ERR] upload failed <code>` => `blinkErr()`
- Always call `http.end()`.

#### LED helpers

- `blinkOk()` -- 1 short blink (success)
- `blinkErr()` -- 2 rapid blinks (failure)
- Always leave `STATUS_LED_PIN` at `LED_OFF` on exit.

#### Serial log format

Matches the prefix convention in `interface-context.md`:

| Event | Example log line |
| ----- | ---------------- |
| AP starting | `[WIFI] starting access point ...` |
| AP up | `[WIFI] AP up — SSID "PlateScope-AP", gateway 192.168.4.1` |
| AP failed | `[ERR] AP start failed` |
| No phone joined | `[ERR] no phone connected to AP — skipping upload` |
| Upload start | `[HTTP] posting dummy JPEG ...` |
| Upload success | `[HTTP] 200 {"ok":true,"plate":"TEST123","confidence":1.0}` |
| Upload failure | `[ERR] upload failed -1` |
| Bounce ignored | `[DBG] bounce ignored` |

### `firmware/README.md`

Record and keep updated:

- Board: AI-Thinker ESP32-CAM + ESP32-CAM-MB baseboard
- Arduino IDE version
- ESP32 board package: name + version (e.g. `esp32 by Espressif Systems 3.x.x`)
- Libraries used this unit: `WiFi` (built-in), `HTTPClient` (built-in)
- Flashing steps: select board, hold BOOT, press RST, click Upload, release BOOT

## Dependencies

- `WiFi.h` -- built-in to the Arduino-ESP32 core
- `HTTPClient.h` -- built-in to the Arduino-ESP32 core
- No additional library installs required for this unit

## Verify When Done

- [ ] Sketch compiles without warnings against the AI-Thinker ESP32-CAM board
      target in Arduino IDE.
- [ ] Board boots; serial shows `[WIFI] AP up — SSID ...` and the phone can see
      and join that Wi-Fi network.
- [ ] With the phone joined and `python app.py` running, press BOOT -> serial
      shows `[HTTP] posting dummy JPEG ...` then
      `[HTTP] 200 {"ok":true,"plate":"TEST123","confidence":1.0}`.
- [ ] Status LED blinks once (short) on success, twice (rapid) on failure.
- [ ] Repeat presses within `DEBOUNCE_MS` log `[DBG] bounce ignored` and do not
      trigger an upload.
- [ ] `firmware/secrets.h` is gitignored; `secrets.h.example` is committed with
      placeholder values only.
- [ ] All GPIO numbers come from `pins.h`; no raw integer pin numbers appear in
      `platescope.ino`.
- [ ] `progress-tracker.md` updated to mark Unit 02 complete.
