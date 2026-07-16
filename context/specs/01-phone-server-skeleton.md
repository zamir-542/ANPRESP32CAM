# Unit 01: Phone Server Skeleton — Upload Endpoint + Dashboard Shell

## Goal

A Flask app that runs in Termux on the phone, accepts a JPEG at `POST /upload`
(enforcing a size cap and a guarded decode), saves it, logs the read, and returns
a **stub** plate result — and serves a dark, mobile-first, auto-refreshing
dashboard at `GET /` that lists saved captures newest-first. When this is done you
can `curl` a JPEG from the PC and watch it appear on the dashboard. No camera, no
OCR, no localization yet.

## Design / Contract

Implements the phone side of the HTTP contract in `interface-context.md`, with the
recognition stubbed:

- `POST /upload` — `multipart/form-data`, field **`image`** (JPEG bytes).
  - Reject bodies over `MAX_UPLOAD_BYTES` (default **2 MB**) with `413`
    `{"ok":false,"reason":"too_large"}`.
  - Missing `image` part or an undecodable JPEG → `400`
    `{"ok":false,"reason":"bad_image"}`.
  - On success: save the image, append a log row, return `200`
    `{"ok":true,"plate":"TEST123","confidence":1.0}` (stub — real value comes in
    Unit 05).
- `GET /` — dashboard HTML: newest-first cards, each with the saved image
  thumbnail (`GET /captures/<id>.jpg`), the (stub) plate text, confidence, and
  timestamp. Empty state when there are no reads. Auto-refresh every few seconds.
- `GET /captures/<id>.jpg` — serve the saved image for a logged read, only from
  within `phone/captures/`.

This unit fixes the **security posture** for every later unit: size cap, guarded
decode, and binding to the LAN only.

## Implementation

### `phone/app.py` (Flask)

- Constants at the top: `MAX_UPLOAD_BYTES = 2 * 1024 * 1024`, `CAPTURES_DIR`,
  `DB_PATH` (or JSON log path), `HOST = "0.0.0.0"`, `PORT = 8000`. Set Flask's
  `MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES` so oversized bodies are rejected before
  buffering.
- `POST /upload`:
  1. Get the `image` part from `request.files`; if absent → `400 bad_image`.
  2. Read bytes; decode with OpenCV (`cv2.imdecode`) or Pillow inside a
     `try/except`. On failure → `400 bad_image`.
  3. Generate an `id` (timestamp-based or a short uuid). Save the original bytes
     to `CAPTURES_DIR/<id>.jpg`.
  4. Insert a log row: `id`, `plate="TEST123"`, `confidence=1.0`,
     `created_at=<iso timestamp>`.
  5. Return `200 {"ok":true,"plate":"TEST123","confidence":1.0}`.
- `GET /captures/<id>.jpg`: `send_from_directory(CAPTURES_DIR, ...)` with the id
  sanitized so it cannot escape the directory; `404` if missing.
- `GET /`: query the log newest-first, render `templates/dashboard.html`.
- Bind with `app.run(host=HOST, port=PORT)` — LAN-only, no debug reloader in the
  committed run command. Register an error handler so `413` returns the JSON body.

### Local log (`phone/`)

- Simplest store that works in Termux — prefer stdlib **`sqlite3`** with a single
  table `reads(id TEXT PRIMARY KEY, plate TEXT, confidence REAL, created_at
  TEXT)`; a flat JSON file is an acceptable fallback. Create the table/file on
  startup if missing.

### `phone/templates/dashboard.html`

- Dark, mobile-first. A newest-first list of read cards: thumbnail
  (`/captures/<id>.jpg`), plate text (large, monospace), confidence, timestamp.
- Empty state: "No captures yet — press BOOT on the camera."
- Auto-refresh: a `<meta http-equiv="refresh" content="3">` is sufficient for the
  shell.
- Footer redaction reminder: "Published screenshots must blur plate digits."

### `phone/` supporting files

- `phone/requirements.txt`: `flask` (+ `opencv-python-headless` or `pillow` for
  the decode — pick one and note it).
- `phone/README.md`: Termux setup (`pkg install python`, `pip install -r
  requirements.txt`), how to run (`python app.py`), and how to find the phone's
  LAN IP (for the firmware's `secrets.h` in Unit 02).
- Root `.gitignore`: `phone/captures/`, the log file (`*.db` / `*.json` log),
  `firmware/secrets.h`.

## Dependencies

- flask (web server + dashboard + upload handling)
- opencv-python-headless **or** pillow (guarded JPEG decode — choose one)
- Python stdlib `sqlite3` (local log; no install)

## Verify when done

- [ ] `python app.py` starts in Termux (or on the PC for first testing) and binds
      on `0.0.0.0:8000`.
- [ ] `curl -F "image=@sample.jpg" http://<host>:8000/upload` returns
      `200 {"ok":true,"plate":"TEST123","confidence":1.0}` and the image appears
      on the dashboard.
- [ ] Posting a >2 MB body returns `413`; posting with no `image` part or a
      non-image returns `400` — the server does not 500 or crash.
- [ ] `GET /` shows saved captures newest-first with thumbnail + stub text +
      timestamp, auto-refreshes, and shows the empty state when the log is empty.
- [ ] `GET /captures/<id>.jpg` serves a saved crop and cannot escape
      `phone/captures/`.
- [ ] `phone/captures/`, the log file, and `firmware/secrets.h` are gitignored;
      no captured image or plate data is committed.
- [ ] No errors/warnings on a clean run; `progress-tracker.md` updated to mark
      Unit 01 complete.
