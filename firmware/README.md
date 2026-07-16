# PlateScope Firmware

## Board

- **Module:** AI-Thinker ESP32-CAM (OV2640, 4 MB PSRAM)
- **Baseboard:** ESP32-CAM-MB (provides USB flashing, BOOT button, and 5 V USB power)

## Toolchain Versions

<!-- Update these when you flash. There is no lockfile for Arduino IDE projects. -->

| Item | Version |
| ---- | ------- |
| Arduino IDE | _fill in_ |
| ESP32 board package (`esp32` by Espressif Systems) | _fill in_ |
| `WiFi` library | built-in to ESP32 core |
| `HTTPClient` library | built-in to ESP32 core |

## Flashing Steps

1. In Arduino IDE: **Tools → Board → AI Thinker ESP32-CAM** (or equivalent).
2. Set **Tools → Port** to the COM port of the ESP32-CAM-MB.
3. Hold the **BOOT** button on the MB board.
4. Press **RST** briefly, then release it.
5. Click **Upload** in Arduino IDE.
6. Once "Connecting…" appears, release **BOOT**.
7. After upload completes, press **RST** to run the new firmware.
8. Open **Serial Monitor** at **115200 baud** to see log output.

## First-Time Setup (SoftAP + camera, Unit 03)

The ESP32 makes its **own** Wi-Fi network (no router/SIM/internet) *and* serves a
camera endpoint. The phone joins the network and pulls photos on demand. **There
is no physical button** — GPIO 0 is the camera clock, so capture is triggered
from the phone dashboard.

1. Copy `firmware/platescope/secrets.h.example` → `firmware/platescope/secrets.h`.
2. Fill in `AP_SSID` / `AP_PASSWORD` (the network the ESP32 broadcasts; password
   ≥ 8 chars). (`SERVER_IP` is unused from Unit 03 — the phone pulls from the
   ESP32 at the fixed `192.168.4.1`.)
3. Flash the firmware and open Serial Monitor at 115200.
4. On the phone: **Wi-Fi settings → join the `AP_SSID` network** (Android warns
   "no internet" — stay connected).
5. In Termux: `cd phone && python app.py`. Open `http://localhost:8000/`.
6. Tap **📷 Capture** on the dashboard → a real photo appears.

### Known compile snags (version-sensitive)

If the sketch fails to compile, it's almost always one of these ESP32-core
version differences — a one-line fix:

- **`pin_sccb_sda` / `pin_sccb_scl`**: newer cores (3.x) use `sccb`; older cores
  (2.x) use `sscb`. Swap the two letters if the compiler complains about those
  fields.
- **`grab_mode` / `CAMERA_GRAB_LATEST`**: if unknown on an older core, delete the
  `config.grab_mode = ...` line.

### Bench gotcha

Firing the flash LED at full brightness during capture can **brown out** the
board on weak USB power (random resets). If capture crashes/reboots the ESP32,
use a better USB cable/port; flash-intensity tuning comes in Unit 06.

## Expected Serial Output (Unit 03)

```
PlateScope — Unit 03: camera capture (SoftAP + pull)
[WIFI] starting access point ...
[WIFI] AP up — SSID "PlateScope-AP", gateway 192.168.4.1
[CAM] init ok
[HTTP] capture server on http://192.168.4.1/capture
[SYS] ready — connect the phone to the AP and tap Capture
[CAM] captured 41235 bytes
```

## File Layout

```
firmware/
  platescope/
    platescope.ino     ← main sketch
    pins.h             ← all GPIO numbers and timing constants (invariant #1)
    secrets.h          ← gitignored; WiFi creds + phone IP
    secrets.h.example  ← committed template with placeholder values
  README.md            ← this file
```
