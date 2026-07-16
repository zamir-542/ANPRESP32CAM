# Code Standards

## General

- Keep the two boundaries (`firmware/` and `phone/`) strictly separate. They
  communicate only through the HTTP contract in `interface-context.md` — never
  share code, assumptions, or magic constants across the boundary.
- Fix root causes, not symptoms. Do not layer retries or sleeps over a real bug.
- One concern per file. The Flask I/O (`app.py`) stays separate from the
  recognition logic (`pipeline.py`).
- Prefer small, verifiable increments that match the current unit's spec.

## Firmware (Arduino-ESP32, C++)

- **Every GPIO number and hardware constant lives in `firmware/pins.h`.** No
  magic pin numbers anywhere else (invariant #1).
- **The BOOT-button ISR only sets a `volatile` flag** — no camera, HTTP, serial,
  or delay calls in interrupt context (invariant #2). Debounce and all real work
  happen in `loop()`.
- WiFi SSID/password and the phone IP live in `firmware/secrets.h`, which is
  gitignored. Provide a committed `secrets.h.example` with placeholder values.
- Fire the flash LED only for the brief capture window; always return it to off.
- Serial logging at 115200, phase-prefixed (see `interface-context.md`). Log
  every capture, upload, and error with enough context to diagnose.
- Record the Arduino-ESP32 core version and any library versions in
  `firmware/README.md` — there is no lockfile.

## Phone (Python, Flask + OpenCV)

- Type-hint public functions. The pipeline's public surface is small and explicit
  (e.g. `recognize(jpeg_bytes) -> Result`).
- **All tunable constants live at the top of `pipeline.py`** as named constants:
  the Malaysian plate regex, min/max plate aspect ratio, min contour area, OCR
  confidence threshold, size cap, etc. No inline magic numbers.
- Validate the uploaded JPEG at the boundary: enforce the size cap, then decode
  inside a guarded path; a decode failure returns a `400`, never an unhandled
  exception (see error handling).
- The Malaysian-format check is the gate: a string that fails the regex is
  returned as `no_plate`, never as a plate (invariant #6).
- Keep `app.py` thin — request parsing, calling `pipeline.recognize`, persisting
  the read, rendering the dashboard. All CV/OCR lives in `pipeline.py`.
- Bind the server to the LAN only; never add a public tunnel or port-forward.

## Reproducibility & Config

- Pin the chosen OCR engine and its version once the Unit 04 spike settles it;
  record it in `phone/README.md` along with the Termux setup steps (`pkg`/`pip`
  commands), since Termux installs are the fragile part.
- Python deps in `phone/requirements.txt` where pip-installable; Termux `pkg`
  prerequisites documented in `phone/README.md`.

## Naming & Style

- Python: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE`
  constants. C++: `camelCase` functions, `UPPER_SNAKE` pin/constant macros.
- Plate strings are normalized to uppercase, spaces stripped, before validation,
  storage, and display.
- No hardcoded magic numbers — name the constant and put it where the standard
  above says it belongs.

## Error Handling

- Fail loudly at boundaries. The firmware logs upload failures over serial with
  the HTTP status/error code; it does not silently drop a capture.
- The server never 500s on bad input: missing `image` part, oversized body, or an
  undecodable JPEG each map to a defined `4xx` with a `{ok:false, reason}` body.
- A "no plate found" result is a normal `200 {ok:false, reason:"no_plate"}`, not
  an error — the demo must degrade gracefully, not crash.

## File Organization

- `firmware/` — the Arduino sketch, `pins.h`, `secrets.h` (gitignored) +
  `secrets.h.example`, and `firmware/README.md` (pinned versions, flashing steps).
- `phone/` — `app.py` (Flask), `pipeline.py` (CV + OCR + validation + constants),
  `templates/` + `static/` (dashboard), `captures/` (gitignored), the log file
  (gitignored), `requirements.txt`, and `phone/README.md` (Termux setup).
- `context/` — planning and spec docs.
- `.gitignore` at the root covers `secrets.h`, `phone/captures/`, the log file,
  and any raw images.
