# Unit 03: Camera Capture — Real Flash-Lit JPEG Over the Wire

## Goal

Replace the Unit 02 dummy JPEG with a **real OV2640 photo**, triggered from the
phone. Tapping a **Capture** button on the dashboard makes the phone fetch a
fresh, flash-lit frame from the ESP32 and show it in the log. When this is done,
pressing Capture displays an actual photo (of whatever the camera points at) on
`http://localhost:8000/`. OCR is still stubbed (`TEST123`) — real recognition is
Unit 05.

## Why the trigger changed (read first)

On the AI-Thinker board **GPIO 0 is the camera's XCLK clock**, so once the camera
is initialized the BOOT button on GPIO 0 can no longer be read. Unit 03 therefore
**removes the physical-button trigger entirely** (ISR, debounce, `DUMMY_JPEG`, and
the `doUpload()` push all go) and moves the trigger to the phone dashboard. This
resolves the GPIO 0 conflict by design.

## Design / Contract

New data flow (**pull** model — see `interface-context.md`):

1. Dashboard **Capture** button → `POST /trigger` on the phone (Flask).
2. Flask `/trigger` → HTTP `GET http://192.168.4.1/capture` on the ESP32.
3. ESP32 `/capture` → flash on → grab one JPEG frame → **return the JPEG bytes**
   (`Content-Type: image/jpeg`) → flash off.
4. Flask receives the JPEG, applies the **same** guarded-decode + size-cap as
   `/upload`, saves it to `captures/`, logs a (stub) read, returns JSON.
5. Dashboard auto-refresh shows the new photo.

- The ESP32 is now an **HTTP server** (`WebServer` on port 80) *and* still the
  SoftAP. Its AP IP is the fixed gateway **`192.168.4.1`**.
- `/upload` (Unit 01/02) is **kept as a test-only endpoint** (curl a JPEG to it
  without the board). The real flow uses `/trigger`.

## Implementation

### Firmware — `firmware/platescope/pins.h` (add camera pins)

Add the fixed AI-Thinker OV2640 pin map (invariant #1 — all GPIO live here). These
are hardware-fixed; do not change them:

```cpp
// ── Camera (AI-Thinker OV2640) — fixed mapping, do not reassign ──────────────
constexpr int PWDN_GPIO_NUM  = 32;
constexpr int RESET_GPIO_NUM = -1;   // not wired
constexpr int XCLK_GPIO_NUM  =  0;   // also the old BOOT pin — now camera-owned
constexpr int SIOD_GPIO_NUM  = 26;
constexpr int SIOC_GPIO_NUM  = 27;
constexpr int Y9_GPIO_NUM    = 35;
constexpr int Y8_GPIO_NUM    = 34;
constexpr int Y7_GPIO_NUM    = 39;
constexpr int Y6_GPIO_NUM    = 36;
constexpr int Y5_GPIO_NUM    = 21;
constexpr int Y4_GPIO_NUM    = 19;
constexpr int Y3_GPIO_NUM    = 18;
constexpr int Y2_GPIO_NUM    =  5;
constexpr int VSYNC_GPIO_NUM = 25;
constexpr int HREF_GPIO_NUM  = 23;
constexpr int PCLK_GPIO_NUM  = 22;

// ── Camera capture settings (tunable in Unit 06) ────────────────────────────
constexpr uint32_t XCLK_FREQ_HZ    = 20000000;  // 20 MHz
constexpr int      JPEG_QUALITY     = 12;        // lower = better/larger
constexpr uint32_t FLASH_SETTLE_MS  = 120;       // flash on → let AE settle
constexpr uint16_t CAM_HTTP_PORT    = 80;
```

`BOOT_BTN_PIN`, `DEBOUNCE_MS`, and the upload-push constants
(`UPLOAD_PORT`/`UPLOAD_PATH`) may be removed — the ESP32 no longer pushes.

### Firmware — `firmware/platescope/platescope.ino`

Remove: the BOOT ISR (`onBootBtn`), debounce state, `DUMMY_JPEG[]`, `doUpload()`,
and the button/interrupt setup. Keep: SoftAP bring-up, the status-LED helpers.

Add:
- `#include "esp_camera.h"` and `#include <WebServer.h>`.
- `WebServer server(CAM_HTTP_PORT);`
- `initCamera()` — build a `camera_config_t` from the pins above,
  `pixformat = PIXFORMAT_JPEG`, `frame_size = FRAMESIZE_SVGA` (800×600 start),
  `jpeg_quality = JPEG_QUALITY`, `fb_count = 2` (PSRAM present),
  `fb_location = CAMERA_FB_IN_PSRAM`. Call `esp_camera_init(&config)`; on failure
  log `[ERR] camera init 0x..` and blink error.
- `handleCapture()`:
  1. Flash on: `digitalWrite(FLASH_LED_PIN, HIGH); delay(FLASH_SETTLE_MS);`
  2. `camera_fb_t* fb = esp_camera_fb_get();`
  3. If `!fb` → flash off → `server.send(500, "text/plain", "capture failed")`.
  4. Else → `server.setContentLength(fb->len);` →
     `server.send(200, "image/jpeg", "");` →
     `server.sendContent((const char*)fb->buf, fb->len);` (stream the buffer).
  5. `esp_camera_fb_return(fb);` → flash off → `blinkOk()`.
  6. Serial: `[CAM] captured <len> bytes`.
- `setup()`: SoftAP (unchanged) → `initCamera()` →
  `server.on("/capture", HTTP_GET, handleCapture); server.begin();` → log
  `[HTTP] capture server on http://192.168.4.1/capture`.
- `loop()`: `server.handleClient();` (nothing else).

Flash LED (GPIO 4) must always end **off**, including on any error path.

### Phone — `phone/app.py`

- Add constants: `ESP32_CAPTURE_URL = "http://192.168.4.1/capture"`,
  `CAPTURE_TIMEOUT_S = 10`. (192.168.4.1 is the fixed AP gateway — not a secret.)
- Factor the Unit 01 save+log tail of `/upload` into a shared helper
  `store_capture(raw_bytes) -> dict` (guarded decode, size check, save to
  `captures/`, insert log row, return the JSON dict). Have `/upload` call it.
- Add `POST /trigger`:
  1. `urllib.request.urlopen(ESP32_CAPTURE_URL, timeout=CAPTURE_TIMEOUT_S)`.
  2. `raw = resp.read(MAX_UPLOAD_BYTES + 1)`; if `len(raw) > MAX_UPLOAD_BYTES` →
     `413 too_large`.
  3. On `URLError`/timeout → `502 {"ok":false,"reason":"camera_unreachable"}`.
  4. Else → `store_capture(raw)` → return its JSON.
  - Use stdlib `urllib`/`socket` only — **no new dependency** on Termux.

### Phone — `phone/templates/dashboard.html`

- Add a **Capture** button at the top. On click, `fetch('/trigger', {method:
  'POST'})`, show a transient "Capturing…" state, then reload on success or show
  the `reason` on failure. Keep the 3-second auto-refresh.

## Dependencies

- `esp_camera.h` — bundled with the ESP32 Arduino core (no install).
- `WebServer.h` — bundled with the ESP32 Arduino core (no install).
- Phone: stdlib `urllib` (no install; **do not** add `requests`).

## Verify when done

- [ ] Sketch compiles for AI-Thinker ESP32-CAM; serial shows AP up **and**
      `[HTTP] capture server on http://192.168.4.1/capture`.
- [ ] Phone joined to `PlateScope-AP`, `python app.py` running. Tapping
      **Capture** on the dashboard shows a **real photo** (crop of the scene),
      newest-first, within a couple of seconds.
- [ ] The flash LED fires at capture and is **off** afterward (and after errors).
- [ ] Browser hitting `http://192.168.4.1/capture` directly returns a JPEG.
- [ ] Camera unreachable (server up, board off) → dashboard shows a graceful
      `camera_unreachable`, no crash; `/upload` still works via curl.
- [ ] All camera GPIO numbers live in `pins.h`; none in the `.ino`.
- [ ] Flash LED off state guaranteed on every path; no secrets added to git.
- [ ] `progress-tracker.md` updated to mark Unit 03 complete.
```
