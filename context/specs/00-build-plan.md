# Build Plan

Units in build order. Each unit produces one visible, verifiable result, stays
within one system boundary (unless noted), and can be built in a single focused
session.

Ordering rules applied:
1. Dependencies first — never build on something that doesn't exist yet.
2. Security/safe-posture before functionality (input caps, no-secrets, LAN-only).
3. The receiving surface + output shell before real data flows into it.
4. Shells/placeholders before real capture or real recognition.
5. Install dependencies just-in-time, in the unit that first needs them.

## Unit 01: Phone Server Skeleton — Upload Endpoint + Dashboard Shell
- **Builds:** A Flask app runnable in Termux. `POST /upload` accepts a
  `multipart/form-data` JPEG (field `image`), enforces the size cap, decodes it
  safely, saves it into `phone/captures/`, records a row in the local log, and
  returns a **stub** `200 {"ok":true,"plate":"TEST123","confidence":1.0}`.
  `GET /` renders a dark, mobile-first, newest-first dashboard of logged captures
  (crop thumbnail + placeholder text + timestamp, auto-refresh). `GET
  /captures/<id>.jpg` serves saved crops. Verified by `curl`-posting a JPEG from
  the PC. **No OCR, no localization.**
- **Depends on:** none
- **Boundary:** `phone/`
- **Installs:** Flask (just-in-time); Termux Python environment.
- **Why first:** It is the receiving surface *and* the output shell. It fixes the
  HTTP contract, the Termux Python environment, and the security posture (size
  cap, guarded decode, LAN-only bind) before any real device or model exists.

## Unit 02: Firmware Skeleton — WiFi Join + BOOT-Triggered Upload (placeholder payload)
- **Builds:** An Arduino sketch with `pins.h` as the single source of hardware
  truth and an untracked `secrets.h` (+ committed `secrets.h.example`). WiFi join
  logged over serial; a debounced BOOT-button (GPIO 0) ISR that only sets a flag;
  on press, a hardcoded/dummy JPEG buffer is POSTed to the phone's `/upload`;
  status blink on GPIO 33; serial logging at 115200. **No camera yet.**
- **Depends on:** Unit 01
- **Boundary:** `firmware/`
- **Installs:** none (Arduino-ESP32 core + built-in `WiFi`/`HTTPClient`).
- **Why here:** Proves the board flashes, joins WiFi, and the ESP32→phone contract
  works end to end with a placeholder payload before the camera is involved.
  Establishes invariants #1 (pins in one header), #2 (no ISR work), #3 (secrets
  out of git).

## Unit 03: Camera Capture — Real Flash-Lit JPEG Over the Wire
- **Builds:** `esp32-camera` init on PSRAM; flash LED (GPIO 4) fired at capture;
  one OV2640 JPEG captured per button press; the **real** frame POSTed to
  `/upload` (replacing Unit 02's dummy buffer). The captured photo is eyeballed in
  the dashboard. Stub OCR still returns `TEST123`.
- **Depends on:** Units 01, 02
- **Boundary:** `firmware/`
- **Why here:** Completes the capture → transfer half of the system; the dashboard
  now shows real photos. This is the data the recognition pipeline will consume.

## Unit 04: OCR Feasibility Spike — Get an OCR Engine Working in Termux
- **Builds:** In isolation, install and prove an OCR engine that actually runs in
  Termux. Start with **Tesseract** (`pkg install tesseract` + `pytesseract`);
  escalate to **EasyOCR** or **PaddleOCR-ONNX** only if plate accuracy is poor.
  Feed it a handful of known, manually cropped plate images; measure raw read
  accuracy. Decide the engine and expose a single function `read_text(crop) ->
  (text, confidence)`.
- **Depends on:** Unit 03 (provides real crops to test on) — but is otherwise
  self-contained.
- **Boundary:** `phone/` (a standalone script, not yet wired into `app.py`).
- **Installs:** the chosen OCR engine (just-in-time).
- **Why a dedicated unit:** Installing a capable OCR engine in Termux is the single
  biggest environment risk. De-risk it alone — like LeafScope isolates
  quantization — so a failure here is never blamed on the pipeline.

## Unit 05: Localization + Validation Pipeline — The Milestone
- **Builds:** `pipeline.py` with `recognize(jpeg_bytes) -> Result`: OpenCV
  localization (grayscale → blackhat/edges → contours → aspect-ratio/area filter →
  candidate crops) → `read_text` on each candidate (Unit 04) → validate against
  the Malaysian plate regex → pick the best **valid** plate. Wired into `/upload`,
  replacing the Unit 01 stub. Holds **all** tunable constants at the top. Enforces
  invariant #6 (never report an invalid plate as confident).
- **Depends on:** Units 03, 04
- **Boundary:** `phone/`
- **Installs:** OpenCV (just-in-time, if not already present).
- **This is the milestone:** press → flash → capture → POST → localize → OCR →
  validated plate on the dashboard. Success criteria 1 and 3 are verified here.

## Unit 06: Accuracy Tuning + Redaction on Real Consenting-Car Captures
- **Builds:** With a small set of real captures from own/consenting vehicles: tune
  localization/OCR thresholds, add preprocessing (deskew, contrast/CLAHE), handle
  "no plate found" gracefully, and confirm the one clean end-to-end demo works
  reliably. Add a **blur/redaction helper** for producing publishable screenshots
  (invariant #5).
- **Depends on:** Unit 05
- **Boundary:** `phone/`
- **Why here:** Turns "it decoded one plate once" into "it demos reliably", and
  builds the redaction step the portfolio writeup depends on.

## Unit 07: Portfolio Writeup
- **Builds:** A root `README.md` telling the story: the distributed-edge design,
  the capture-vs-compute split, the ESP32↔phone HTTP contract, the OpenCV+OCR
  pipeline, Malaysian-format validation, a **blurred** demo GIF/screenshot, honest
  accuracy notes, the privacy stance, and pinned versions (Arduino core, Python
  deps, OCR engine).
- **Depends on:** Unit 06
- **Boundary:** repo root
- **Why a unit:** For a portfolio project, the writeup *is* the deliverable — it is
  built deliberately, not as an afterthought.
