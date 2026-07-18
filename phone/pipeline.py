"""Recognition pipeline: a captured frame -> a validated Malaysian plate.

`recognize(jpeg_bytes) -> Result` is the whole recognition surface (Unit 05).
It localizes candidate plate regions with classical OpenCV, reads each with
Tesseract (ocr.read_text, Unit 04), validates against the Malaysian plate
format, and returns the best valid plate — or nothing.

All CV/OCR lives here; app.py holds no recognition logic (code-standards).
Every tunable is a named constant at the top of this file — no inline magic
numbers. Localization is a first-pass classical approach; its thresholds are
the Unit 06 tuning knobs.

Invariant #6: a string that fails MALAYSIAN_PLATE_RE is never returned as a
plate — recognize() reports no plate (Result.plate is None) instead.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from ocr import read_text

# --- Debug / observability (Unit 06) ----------------------------------------
# Off by default. Turn on with `PLATESCOPE_DEBUG=1 python app.py` (or before
# running the batch harness). When on, recognize() prints per-candidate reads
# to stderr and saves the frame + candidate crops of a no_plate miss under
# DEBUG_DIR — turning an opaque "No plate found" into "localization found 0
# boxes" vs "found a box, OCR read 'GHV44' @0.42, rejected". Normal runs are
# unaffected: no stderr noise, no disk writes, same return values.
DEBUG = os.environ.get("PLATESCOPE_DEBUG") == "1"
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")


def _debug(msg: str) -> None:
    if DEBUG:
        print(f"[recognize] {msg}", file=sys.stderr)


def _save_debug_frame(bgr: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> None:
    """Save a no_plate frame + its localized crops for eyeballing (DEBUG only)."""
    stamp = time.strftime("%Y%m%dT%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    out = os.path.join(DEBUG_DIR, stamp)
    os.makedirs(out, exist_ok=True)
    cv2.imwrite(os.path.join(out, "frame.jpg"), bgr)
    for i, box in enumerate(boxes):
        crop = _crop(bgr, box)
        if crop.size:
            cv2.imwrite(os.path.join(out, f"box{i}.jpg"), crop)
    _debug(f"saved no_plate artifacts to {out}")

# --- Tunables (single source of truth) --------------------------------------
# Malaysian Peninsular format: 1-3 letters, 1-4 digits, optional trailing
# letter (interface-context.md). The ONE place this pattern is defined.
MALAYSIAN_PLATE_RE = re.compile(r"^[A-Z]{1,3}[0-9]{1,4}[A-Z]?$")

# Localization runs on a downscaled copy for stable thresholds; crops are
# taken from the full-resolution frame so OCR sees full detail.
WORK_WIDTH = 640  # px width of the localization working image

# A single-row plate blob is much wider than tall. Boxes outside this
# aspect-ratio band, or smaller than this fraction of the frame, are dropped.
MIN_ASPECT = 2.0
MAX_ASPECT = 6.0
MIN_AREA_FRAC = 0.01  # box area must be >= 1% of the frame

# Wide rectangular kernel closes the gaps between character edges into one
# plate-sized blob (width >> height, matching a plate's shape).
CLOSE_KERNEL = (25, 7)

MAX_CANDIDATES = 5      # localized boxes to OCR, best-ranked first
CROP_PAD_FRAC = 0.08    # padding around a localized box before cropping

# A read is only accepted if it clears this confidence AND matches the regex.
# On-device screen captures of BHV33 separated cleanly by confidence: correct
# reads 0.77 / 0.85, format-valid misreads (GHV44, B33) 0.42 / 0.48. 0.60
# threads that gap — the misreads become no_plate (better than a confident
# wrong plate, invariant #6) while correct reads pass with margin. Provisional:
# laptop-screen data; re-tune on real plates in Unit 06.
OCR_CONFIDENCE_MIN = 0.60

JPEG_QUALITY = 90  # quality of the saved plate-crop thumbnail


@dataclass
class Result:
    """Outcome of recognize(). plate is None => no valid plate found."""

    plate: str | None
    confidence: float
    crop_jpeg: bytes | None


def _localize(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return candidate plate bounding boxes (x, y, w, h) in full-res coords.

    Boxes are ranked largest-first and capped at MAX_CANDIDATES.
    """
    h0, w0 = bgr.shape[:2]
    scale = WORK_WIDTH / float(w0) if w0 > WORK_WIDTH else 1.0
    work = cv2.resize(bgr, (int(w0 * scale), int(h0 * scale))) if scale != 1.0 else bgr

    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)  # denoise, keep edges

    # Vertical-stroke emphasis: characters produce many strong vertical edges.
    # Sobel-x is polarity-agnostic (works for light-on-dark and dark-on-light
    # plates alike).
    grad = np.absolute(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    grad = cv2.convertScaleAbs(grad)
    grad = cv2.GaussianBlur(grad, (5, 5), 0)
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE_KERNEL)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    closed = cv2.dilate(closed, None, iterations=2)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    work_area = work.shape[0] * work.shape[1]
    inv = 1.0 / scale  # map work-image coords back to full-res
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h == 0:
            continue
        aspect = w / h
        area_frac = (w * h) / work_area
        if MIN_ASPECT <= aspect <= MAX_ASPECT and area_frac >= MIN_AREA_FRAC:
            boxes.append((int(x * inv), int(y * inv), int(w * inv), int(h * inv)))

    boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
    return boxes[:MAX_CANDIDATES]


def _crop(bgr: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Crop `box` from `bgr` with CROP_PAD_FRAC padding, clamped to the frame."""
    x, y, w, h = box
    pad_x = int(w * CROP_PAD_FRAC)
    pad_y = int(h * CROP_PAD_FRAC)
    frame_h, frame_w = bgr.shape[:2]
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(frame_w, x + w + pad_x)
    y1 = min(frame_h, y + h + pad_y)
    return bgr[y0:y1, x0:x1]


def _bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def _encode_jpeg(bgr: np.ndarray) -> bytes | None:
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return buf.tobytes() if ok else None


def recognize(jpeg_bytes: bytes) -> Result:
    """Localize, read, and validate a plate in a captured JPEG.

    Returns the highest-confidence read that both matches MALAYSIAN_PLATE_RE
    and clears OCR_CONFIDENCE_MIN. If none qualifies, returns an empty Result
    (plate=None) — never a string that fails validation (invariant #6).

    Assumes `jpeg_bytes` is already size-capped and decodable (app.py enforces
    that at the boundary).
    """
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        _debug("decode failed — not a valid image")
        return Result(None, 0.0, None)

    # Localized crops first (ranked), then the whole frame as a last-resort
    # fallback: read_text is strong on tight, plate-filling crops, so this
    # degrades gracefully when localization misses. Every candidate passes the
    # same regex + confidence gate, so the fallback can only add a valid read.
    boxes = _localize(bgr)
    candidates = [(f"box{i} {box}", _crop(bgr, box)) for i, box in enumerate(boxes)]
    candidates.append(("full-frame", bgr))
    _debug(f"localization found {len(boxes)} box(es)")

    best: tuple[float, str, np.ndarray] | None = None
    for label, crop in candidates:
        if crop.size == 0:
            _debug(f"  {label}: empty crop, skipped")
            continue
        text, confidence = read_text(_bgr_to_pil(crop))
        regex_ok = bool(MALAYSIAN_PLATE_RE.match(text))
        conf_ok = confidence >= OCR_CONFIDENCE_MIN
        eligible = regex_ok and conf_ok
        # Strict '>' keeps earlier (localized) candidates on a confidence tie.
        is_best = eligible and (best is None or confidence > best[0])
        if is_best:
            best = (confidence, text, crop)
        if DEBUG:
            if not regex_ok:
                verdict = "reject:format"
            elif not conf_ok:
                verdict = f"reject:conf<{OCR_CONFIDENCE_MIN}"
            else:
                verdict = "accept" + (" *best" if is_best else "")
            _debug(f"  {label}: read='{text}' conf={confidence:.2f} -> {verdict}")

    if best is None:
        _debug("result: no_plate")
        if DEBUG:
            _save_debug_frame(bgr, boxes)
        return Result(None, 0.0, None)
    confidence, plate, crop_bgr = best
    _debug(f"result: {plate} @ {confidence:.2f}")
    return Result(plate=plate, confidence=confidence, crop_jpeg=_encode_jpeg(crop_bgr))
