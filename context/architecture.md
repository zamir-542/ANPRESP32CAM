# Architecture Context

## Stack

| Layer | Technology | Role / Why |
| ----- | ---------- | ---------- |
| Capture firmware | C++ (Arduino-ESP32 core) via the Arduino IDE | Runs on the ESP32-CAM. Chosen for familiarity and simplicity (matches the LeafScope project). Trade-off: no lockfile, so board-package and library versions are recorded manually in the firmware README. |
| Camera driver | `esp32-camera` (OV2640) | Standard driver for the AI-Thinker module; provides the JPEG framebuffer. |
| Upload transport | Arduino `HTTPClient` over WiFi (`WiFi.h`) | Built-in; POSTs the captured JPEG to the phone as `multipart/form-data`. No extra library. |
| Compute runtime | Python 3 in **Termux** (on the phone) | The phone is the edge compute node. Python chosen because the user is Python-fluent and it keeps the CV/OCR pipeline flexible. |
| Web server + dashboard | Flask | Tiny footprint; serves the dashboard and receives uploads in one process. |
| Image / localization | OpenCV (`opencv-python-headless`, or Termux `opencv`) | Plate localization + preprocessing (grayscale, blackhat/edges, contours, crop, deskew). |
| OCR | **TBD by feasibility spike (Unit 04)** | Candidates in order of install-ability: Tesseract (`pkg install tesseract` + `pytesseract`), then EasyOCR / PaddleOCR-ONNX if accuracy demands. The engine is not committed until the spike proves it runs in Termux. |
| Local log | stdlib `sqlite3` (or a JSON file) | Stores read history (plate, confidence, crop path, timestamp) on the phone. Gitignored. |
| Capture hardware | AI-Thinker ESP32-CAM (OV2640, 4MB PSRAM) + ESP32-CAM-MB baseboard | PSRAM holds the JPEG framebuffer; MB board gives USB flashing and a reusable BOOT button. |

## System Boundaries

Two boundaries, joined **only** by one HTTP image-upload contract (see
`interface-context.md`).

- `firmware/` — owns everything on the chip: hosting its own Wi-Fi access point
  (SoftAP) that the phone joins, debounced BOOT-button capture, flash LED, JPEG
  capture, and the HTTP upload to the phone. All GPIO
  numbers live in `firmware/pins.h`; WiFi credentials + the phone's IP live in an
  untracked `firmware/secrets.h`. Knows nothing about OCR or plate formats.
- `phone/` — owns everything on the phone: the Flask server (`app.py`) that
  receives uploads and serves the dashboard, the recognition pipeline
  (`pipeline.py`: OpenCV localization + OCR + Malaysian validation, holds all
  tunable constants), the dashboard templates/static assets, and the local
  captures + log. Knows nothing about GPIO or camera drivers.
- The **contract** between them: `POST /upload` (`multipart/form-data`, JPEG) →
  JSON `{ok, plate, confidence}`. This is the single integration point; it is
  defined once in `interface-context.md` and both sides must match it exactly.

## Data / Storage Model

- **ESP32 flash**: firmware binary. WiFi creds + phone IP compiled in from
  `secrets.h` (never committed).
- **ESP32 RAM/PSRAM**: the JPEG framebuffer at capture time. Nothing persisted
  on-device between captures.
- **Phone — in memory**: the uploaded JPEG bytes during a request (transient).
- **Phone — `phone/captures/`**: saved plate-crop thumbnails, referenced by the
  dashboard. **Gitignored** (contains plate imagery = personal data).
- **Phone — read log** (`sqlite3` file or JSON): one row per read (plate text,
  confidence, crop filename, timestamp). **Gitignored** (personal data).
- No training dataset in v1. No cloud storage. No API keys anywhere.

## Access / Trust Model

- The **uploaded JPEG is untrusted input** — it can be malformed, truncated, or
  oversized. It is size-capped and decoded inside a guarded path; a failed decode
  yields an error response, never a crash.
- The **LAN is the ESP32's own SoftAP** — the ESP32 broadcasts a WPA2-protected
  Wi-Fi network (credentials in `secrets.h`); the phone is its only client. This
  is a new surface vs. a pure station design: anyone with the AP password could
  join. It is acceptable because the system is self-contained and offline, but
  the AP password is a real credential and stays out of git.
- Any **client on that AP can reach the Flask server** — the demo runs without
  auth, but the server binds to the local network only and is **never exposed to
  the internet** (no router, no port-forwarding, no tunnel). Deliberate,
  documented, offline-only posture.
- **Plate numbers and plate images are personal data.** They are stored only
  locally (gitignored) and must be blurred/redacted in any published
  screenshot/GIF.
- **Secrets** (SoftAP SSID/password the ESP32 broadcasts, phone IP): live only in
  untracked `firmware/secrets.h`; never committed. There are no other secrets.

## Invariants

Rules this system must never violate.

1. **All ESP32 GPIO numbers and hardware constants live in one header**
   (`firmware/pins.h`) — no magic pin numbers scattered through the firmware.
2. **No blocking work in the BOOT-button ISR** — the ISR only sets a flag; the
   camera capture and HTTP upload run in the main loop.
3. **Secrets and personal data never enter git** — WiFi credentials and the phone
   IP live only in untracked `firmware/secrets.h`; captured plate images and
   decoded plate strings are gitignored and never committed.
4. **The core capture → recognize → serve flow runs entirely on the ESP32 + phone
   over the LAN** — no code path in the core flow may depend on a cloud service or
   the internet. It is an edge system by definition.
5. **Captured plate images and decoded plate strings are personal data** — stored
   only locally (gitignored) and **blurred/redacted in every published
   screenshot or GIF**.
6. **The pipeline never reports a string that fails Malaysian-format validation
   as a confident plate** — it falls back to "no valid plate found" (analogous to
   LeafScope's confidence floor).
7. **The ESP32↔phone contract is defined once** in `interface-context.md`
   (multipart field name, JPEG payload, JSON response shape); firmware and server
   must match it exactly — neither side invents its own wire format.
