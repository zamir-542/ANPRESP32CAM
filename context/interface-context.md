# Interface Context

PlateScope has three surfaces: the **ESP32-CAM hardware** (pinout + serial), the
**ESP32↔phone HTTP contract** (the single integration point), and the
**phone-served web dashboard**. The Malaysian plate pattern is also defined here
since both validation and the dashboard depend on it.

## Hardware / Embedded (ESP32-CAM)

### Pinout — AI-Thinker ESP32-CAM

All of these live in `firmware/pins.h`; the table below is the reference. Camera
pins are the fixed AI-Thinker OV2640 mapping and must not be reassigned.

| Pin | Function | Notes |
| --- | -------- | ----- |
| GPIO 0 | BOOT button | Capture trigger. Also the flash-mode strap pin — must be high at boot; only read as a button after boot. |
| GPIO 4 | Flash LED | Bright white on-board LED; fired at capture. Active HIGH. |
| GPIO 33 | On-board red status LED | Optional capture/OK/error feedback. **Active LOW.** |
| GPIO 32 | Camera power-down (PWDN) | Managed by the `esp32-camera` driver. |
| GPIO 26 / 27 | Camera SCCB SDA / SCL | I²C-like camera control bus. |
| GPIO 5,18,19,21,36,39,34,35 | Camera data D0–D7 | Fixed OV2640 data bus. |
| GPIO 25 / 23 / 22 | VSYNC / HREF / PCLK | Camera sync/clock. |
| GPIO 0 (XCLK) | Camera master clock | Shared strap pin; driver-owned at runtime. |

> Note: GPIO 0 is both the BOOT button and a boot strap. Read it as a button only
> in the main loop after boot, never gate startup on it.
>
> **⚠ Unit 03 conflict:** on the AI-Thinker board GPIO 0 is *also* the camera
> **XCLK** (master clock). In Unit 02 (no camera) the BOOT button on GPIO 0 works
> fine. Once the camera is initialized in Unit 03, the driver drives GPIO 0 as the
> clock output — so it can no longer be read as a button. The capture **trigger
> for Unit 03 must be decided** (options: a "Capture" button on the phone
> dashboard hitting a tiny ESP32 endpoint — the natural fit for SoftAP; a serial
> keypress; an external button on a free GPIO; or timed auto-capture).

### Serial

- **115200 baud.** Log lines are human-readable and prefixed by phase, e.g.
  `[WIFI] connected 192.168.0.42`, `[CAP] jpeg 24196 bytes`,
  `[HTTP] 200 {"ok":true,"plate":"WXY1234"}`, `[ERR] upload failed -1`.

### Power

- Powered over USB via the ESP32-CAM-MB baseboard (5V). The flash LED draws a
  brief high current at capture — expected; keep the capture pulse short.

## Network Model (SoftAP)

The system runs on the **ESP32's own Wi-Fi access point** — no router, SIM, or
internet. (Chosen because the phone has no SIM to host a hotspot, and shared
networks block device-to-device traffic.)

- **ESP32** = access point + gateway at **`192.168.4.1`**. SSID/password are set
  in `firmware/secrets.h` (`AP_SSID` / `AP_PASSWORD`, WPA2, password ≥ 8 chars).
- **Phone** joins that SSID and, as the only client, gets **`192.168.4.2`** —
  where the Flask server listens. This is `SERVER_IP` in `secrets.h`.
- The phone owner views the dashboard on the phone itself at
  `http://localhost:8000/`, independent of the AP IP.
- If the phone's IP is not `192.168.4.2` (check `ip addr` in Termux), update
  `SERVER_IP` and re-flash.

## The ESP32 ↔ Phone HTTP Contract *(single integration point)*

Defined once here. Firmware (`firmware/`) and server (`phone/`) must match this
exactly (invariant #7).

### `POST /upload`

- **Body:** `multipart/form-data`, one part named **`image`**, containing the raw
  JPEG bytes. Filename/content-type are cosmetic; the server treats the part as
  JPEG.
- **Size cap:** requests over the configured limit (default **2 MB**) are rejected
  with `413`.
- **Success response (200):**
  ```json
  { "ok": true, "plate": "WXY1234", "confidence": 0.87 }
  ```
- **No-plate response (200):**
  ```json
  { "ok": false, "reason": "no_plate" }
  ```
- **Error responses:** `400` (missing `image` part / undecodable JPEG),
  `413` (too large). Body: `{ "ok": false, "reason": "<slug>" }`.
- `plate` is the normalized plate string (uppercase, no spaces). `confidence` is a
  0–1 float from the OCR/validation step.

### `GET /`

- Returns the dashboard HTML (see below).

### `GET /captures/<id>.jpg`

- Returns the saved plate-crop thumbnail for a logged read. `<id>` is the read's
  identifier; the server only serves files from within `phone/captures/`.

### `POST /trigger` *(Unit 03+, the real flow)*

- Fired by the dashboard **Capture** button. The phone fetches a fresh frame from
  the ESP32 (`GET http://192.168.4.1/capture`), then stores + logs it exactly like
  `/upload`. Responses mirror `/upload`, plus `502
  {"ok":false,"reason":"camera_unreachable"}` when the board can't be reached.
- **Direction note:** from Unit 03 the capture is a **pull** — the phone requests
  the image. `/upload` (ESP32→phone push, Unit 02) is retained as a curl-able
  test endpoint only.

### ESP32 endpoint — `GET http://192.168.4.1/capture` *(Unit 03+)*

- The ESP32 runs a `WebServer` on port 80 at its fixed SoftAP gateway IP. On
  `GET /capture` it fires the flash, grabs one OV2640 JPEG, and returns it as
  `Content-Type: image/jpeg` (`500` on capture failure). This is the only endpoint
  the ESP32 serves.

## Malaysian Plate Pattern *(validation + display)*

- **v1 target — common Peninsular format:** 1–3 letters, then 1–4 digits, then an
  optional trailing letter. Examples: `WXY 1234`, `ABC 123`, `WA 1234 B`,
  `BMT 5`.
- **Reference regex** (applied after normalizing to uppercase, spaces stripped):
  ```
  ^[A-Z]{1,3}[0-9]{1,4}[A-Z]?$
  ```
  Store this as a single named constant in `pipeline.py` — never inline it in more
  than one place.
- **Refinements (optional, note as tunables):** Malaysian series generally omit
  the letters `I`, `O`, and `Q` (and `Z` prefixes are reserved for military). A
  stricter character class can be adopted if OCR confusion (`0/O`, `1/I`) hurts
  accuracy.
- **Out of v1 scope:** Sabah/Sarawak divisional formats, diplomatic, military,
  and vanity/special series. Strings that don't match the v1 pattern are reported
  as `no_plate` (invariant #6), not force-fit.

## Software / Web / App (dashboard)

### Theme

- Simple, **dark**, mobile-first — it is viewed on the phone's own browser and in
  portfolio screenshots. Function over flourish; the plate crop and text are the
  focus.

### Layout Patterns

- A newest-first **list of read cards**, each showing: the plate-crop thumbnail,
  the decoded plate (large, monospace), the confidence, and a timestamp.
- An empty state ("No captures yet — press BOOT on the camera").
- **Auto-refresh** every few seconds (meta refresh or a small poll) so a new
  capture appears without manual reload.
- Redaction reminder in the footer: published screenshots must blur plate digits
  (invariant #5).

### Output Format

- The dashboard reads from the local log; the crop images come from
  `GET /captures/<id>.jpg`. No client-side framework required — server-rendered
  HTML is sufficient.
