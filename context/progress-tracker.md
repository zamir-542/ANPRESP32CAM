# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- **Unit 03 — Camera Capture: implemented; phone half verified host-side;
  board-side flash pending.**

## Current Goal

- Flash Unit 03 to the ESP32-CAM and verify on the bench: `[CAM] init ok`, tap
  **Capture** on the dashboard → a real photo appears. Then Unit 04 (OCR spike).

## Completed

- Planning discussion (`/idea`): architecture, scope, invariants, and build plan
  agreed.
- Context files written: `project-overview.md`, `architecture.md`,
  `interface-context.md`, `code-standards.md`, `ai-workflow-rules.md`, this
  tracker.
- Root `CLAUDE.md`, `context/specs/00-build-plan.md`, and
  `context/specs/01-phone-server-skeleton.md` written.
- **Unit 01 — Phone server skeleton.** `phone/app.py` (Flask), `templates/
  dashboard.html`, `requirements.txt`, `README.md`, root `.gitignore`. Decode
  via **Pillow**; log via stdlib **sqlite3**. Verified end-to-end on the PC:
  valid upload → `200 {ok,plate:TEST123,confidence:1.0}`; missing/`bad_image` →
  `400`; oversized → `413`; dashboard renders newest-first + empty state; crop
  served with path-traversal blocked (404); startup creates `captures/` +
  `reads.db`.
- **Unit 02 — Firmware skeleton.** `context/specs/02-firmware-skeleton.md`
  written. `firmware/platescope/platescope.ino`, `pins.h`,
  `secrets.h.example`, `firmware/README.md` created. `.gitignore` broadened to
  `firmware/**/secrets.h`. No camera; dummy JPEG POST to `/upload`.
  - **Bug found & fixed during verification:** the original `DUMMY_JPEG` was a
    truncated JPEG — the phone's Pillow `verify()` rejected it, so `/upload`
    returned `400 bad_image` and the board would have blinked *error*. Replaced
    with a valid 331 B 8×8 baseline JPEG.
  - **Host-side verification done (no board needed):** re-extracted the JPEG
    bytes from the `.ino` and replayed the firmware's exact multipart request
    against the running server → `200 {"ok":true,"plate":"TEST123"}`. A
    control (same hand-rolled framing + a real JPEG) also passed, isolating the
    defect to the payload, not the framing. Static invariant checks #1/#2/#3
    pass.
  - **Connectivity pivoted to SoftAP** (see Architecture Decisions): the ESP32
    now hosts its own Wi-Fi AP instead of joining a network. Firmware, secrets,
    README, spec, `architecture.md`, and `interface-context.md` updated. Wire
    contract re-verified host-side after the rewrite (`200 ok`).
  - **Board-side verified ✅** — flashed the AI-Thinker ESP32-CAM: AP came up,
    phone joined `PlateScope-AP`, BOOT press → `[HTTP] 200 {"ok":true,
    "plate":"TEST123","confidence":1.0}`. (First press failed `-1` only because
    `python app.py` wasn't running yet — expected.)

## In Progress

- **Unit 03 — Camera Capture (board-side flash + verify pending).**
  - Firmware (`platescope.ino`, `pins.h`): SoftAP + `WebServer` on
    `192.168.4.1/capture` (flash → OV2640 JPEG → return `image/jpeg`); button/
    ISR/dummy/push removed. Camera pins added to `pins.h`.
  - Phone (`app.py`, `dashboard.html`): `store_capture()` helper; `POST /trigger`
    pulls from the ESP32 (stdlib `urllib`, no new dep); dashboard **Capture**
    button. `/upload` kept as a curl test endpoint.
  - **Verified host-side (8/8):** /trigger success→TEST123, camera_unreachable
    (502), oversized (413), bad_image (400), /upload still 200, dashboard button
    + card render, row count. (ESP32 mocked by patching `urlopen`.)
  - Watch on the bench: `pin_sccb`/`sscb` core-version field name, `grab_mode`,
    and flash brownout (see `firmware/README.md`).

## Next Up

- **Unit 03 — Camera Capture** (real flash-lit JPEG over the wire): swap
  `DUMMY_JPEG` for the OV2640 framebuffer, add `esp32-camera` init + PSRAM
  buffer, fire GPIO 4 flash LED at capture, eyeball result on dashboard.

## Open Questions

- **OCR engine (Unit 04):** which engine actually installs and performs in
  Termux — Tesseract vs. EasyOCR vs. PaddleOCR-ONNX? Deferred to the Unit 04
  feasibility spike on purpose.
- **Malaysian regex strictness:** whether to exclude `I`/`O`/`Q` letters to
  reduce OCR confusion — decide during Unit 05/06 tuning with real captures.
- ~~**Log store:** SQLite vs. flat JSON~~ — resolved in Unit 01: stdlib
  `sqlite3` (`reads.db`).

## Architecture Decisions

- **Distributed edge split:** ESP32-CAM captures, phone computes. Chosen because
  the phone's own camera is in poor condition and this makes a cleaner "capture
  at the edge, recognize on-device" portfolio story than a laptop host.
- **Classical OpenCV localization + off-the-shelf OCR (no trained model in v1):**
  fastest path to a working demo; avoids a dataset/training effort.
- **Termux Python (Flask + OpenCV):** user is Python-fluent; keeps the pipeline
  flexible. Known risk: installing a good OCR engine in Termux — de-risked early
  in a dedicated Unit 04 spike.
- **LAN-only, no cloud:** required for the "edge / fully offline" claim
  (invariant #4).
- **ESP32 SoftAP for connectivity (Unit 02+):** the ESP32 hosts its own Wi-Fi AP
  (192.168.4.1) and the phone joins it (192.168.4.2). Chosen because the phone
  has no SIM to host a hotspot and the available shared network (`10.202.x.x`)
  blocks device-to-device traffic. Bonus: makes the whole system self-contained
  and demoable anywhere — strengthens the offline-edge story. Trade-off: the
  ESP32 now broadcasts an AP (a new, WPA2-protected surface); the AP password is
  a real credential kept in untracked `secrets.h`.

## Session Notes

- Working project name: **PlateScope** (rename freely).
- Privacy stance: own/consenting vehicles only; blur plate digits in every
  published screenshot/GIF (invariant #5).
- Success bar for v1 is one clean end-to-end demo, not a formal accuracy metric.
