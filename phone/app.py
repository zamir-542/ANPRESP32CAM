"""PlateScope phone server.

Flask app that stores + logs camera captures and serves a dashboard at GET /.
Two ways a capture arrives:
  - POST /trigger  (Unit 03, the real flow): the phone PULLS a fresh frame from
    the ESP32's /capture endpoint, then stores it.
  - POST /upload   (Unit 02, kept as a curl-able test endpoint): a JPEG is pushed
    in as multipart/form-data.

Recognition is still stubbed: every stored capture is logged as plate "TEST123".
Real localization + OCR arrive in Unit 05.

LAN-only: binds to HOST below; never expose this to the internet.
"""

from __future__ import annotations

import io
import os
import socket
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from flask import (
    Flask,
    g,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from PIL import Image, UnidentifiedImageError

# --- Configuration (single source of truth) --------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(BASE_DIR, "captures")
DB_PATH = os.path.join(BASE_DIR, "reads.db")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB hard cap on a stored image
HOST = "0.0.0.0"                    # LAN-only; do not port-forward / tunnel
PORT = 8000

# The ESP32 is the SoftAP gateway at a fixed IP; overridable for host-side tests.
ESP32_CAPTURE_URL = os.environ.get("ESP32_CAPTURE_URL", "http://192.168.4.1/capture")
CAPTURE_TIMEOUT_S = 10

STUB_PLATE = "TEST123"              # placeholder; real plate arrives in Unit 05
STUB_CONFIDENCE = 1.0

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


class BadImage(Exception):
    """Raised when bytes are empty or not a decodable image."""


# --- Local log (sqlite3) ----------------------------------------------------
def get_db() -> sqlite3.Connection:
    """Return a per-request sqlite connection, opening one if needed."""
    conn = getattr(g, "_db", None)
    if conn is None:
        conn = g._db = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    return conn


@app.teardown_appcontext
def close_db(_exc: object) -> None:
    conn = getattr(g, "_db", None)
    if conn is not None:
        conn.close()


def init_storage() -> None:
    """Create the captures dir and the reads table if they don't exist."""
    os.makedirs(CAPTURES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reads (
                id         TEXT PRIMARY KEY,
                plate      TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


# --- Core: validate, save, log a capture ------------------------------------
def store_capture(raw: bytes) -> dict:
    """Guard-decode `raw`, save it, log a (stub) read, return the record.

    Raises BadImage if the bytes are empty or not a decodable image. The caller
    is responsible for enforcing MAX_UPLOAD_BYTES before calling.
    """
    if not raw:
        raise BadImage("empty body")
    try:
        Image.open(io.BytesIO(raw)).verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadImage("undecodable") from exc

    read_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    with open(os.path.join(CAPTURES_DIR, f"{read_id}.jpg"), "wb") as fh:
        fh.write(raw)

    db = get_db()
    db.execute(
        "INSERT INTO reads (id, plate, confidence, created_at) VALUES (?, ?, ?, ?)",
        (read_id, STUB_PLATE, STUB_CONFIDENCE, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return {"id": read_id, "plate": STUB_PLATE, "confidence": STUB_CONFIDENCE}


# --- Routes -----------------------------------------------------------------
@app.post("/trigger")
def trigger():
    """Pull a fresh frame from the ESP32 and store it (the real capture flow)."""
    try:
        with urllib.request.urlopen(ESP32_CAPTURE_URL, timeout=CAPTURE_TIMEOUT_S) as resp:
            raw = resp.read(MAX_UPLOAD_BYTES + 1)
    except (urllib.error.URLError, OSError, socket.timeout):
        return jsonify(ok=False, reason="camera_unreachable"), 502

    if len(raw) > MAX_UPLOAD_BYTES:
        return jsonify(ok=False, reason="too_large"), 413
    try:
        rec = store_capture(raw)
    except BadImage:
        return jsonify(ok=False, reason="bad_image"), 400
    return jsonify(ok=True, plate=rec["plate"], confidence=rec["confidence"]), 200


@app.post("/upload")
def upload():
    """Test-only push endpoint: a JPEG as multipart/form-data field 'image'.

      too large                 -> 413 {"ok":false,"reason":"too_large"}
      missing/undecodable image -> 400 {"ok":false,"reason":"bad_image"}
    """
    file = request.files.get("image")
    if file is None:
        return jsonify(ok=False, reason="bad_image"), 400
    try:
        rec = store_capture(file.read())
    except BadImage:
        return jsonify(ok=False, reason="bad_image"), 400
    return jsonify(ok=True, plate=rec["plate"], confidence=rec["confidence"]), 200


@app.get("/captures/<read_id>.jpg")
def capture(read_id: str):
    """Serve a saved crop.

    os.path.basename strips any path components, and send_from_directory
    itself rejects traversal and returns 404 for a missing file.
    """
    return send_from_directory(CAPTURES_DIR, f"{os.path.basename(read_id)}.jpg")


@app.get("/")
def dashboard():
    db = get_db()
    reads = db.execute(
        "SELECT id, plate, confidence, created_at FROM reads ORDER BY created_at DESC"
    ).fetchall()
    return render_template("dashboard.html", reads=reads)


@app.errorhandler(413)
def too_large(_err: object):
    return jsonify(ok=False, reason="too_large"), 413


if __name__ == "__main__":
    init_storage()
    # No debug reloader: this is the committed run command.
    app.run(host=HOST, port=PORT)
