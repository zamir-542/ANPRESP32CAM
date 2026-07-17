"""Unit 04 — OCR feasibility spike.

Standalone script (not imported by app.py). Proves an OCR engine actually
runs in Termux and measures its raw read accuracy on real plate crops.

Engine: Tesseract via pytesseract — the build plan's first choice
(context/specs/00-build-plan.md, Unit 04). Escalate to EasyOCR or
PaddleOCR-ONNX only if the accuracy measured here is poor; if that happens,
update this docstring and architecture.md with the new choice.

Usage:
    python ocr_spike.py <crops_dir>

Each file in <crops_dir> is a single plate crop (JPEG/PNG). If a filename
encodes the expected plate text before the first underscore (e.g.
"WXY1234.jpg" or "WXY1234_02.jpg"), the script scores the OCR read against it
and prints a final accuracy summary. Unscored files are still OCR'd and
printed for eyeballing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytesseract
from PIL import Image

# --- Tunables (single source of truth for this spike) -----------------------
# No single PSM (page segmentation mode) generalizes across hand-cropped
# plate images: framing varies crop to crop (tight vs. padded, letters/digits
# glued together vs. gapped), and real-device testing found crops that came
# back "Empty page!!" under one PSM but read correctly under another. Try
# each candidate and keep the best result. Order: single line, single word,
# uniform block, sparse text.
CANDIDATE_PSMS = (7, 8, 6, 11)

# No character whitelist: confirmed on real-device testing (Tesseract 5.5.2)
# that `-c tessedit_char_whitelist=...` still reads correct text but zeroes
# out confidence on the LSTM engine (a real 0, not "-1 no data") — a whitelist
# predates LSTM and doesn't integrate cleanly with it. Dropping it restored
# real confidence scores with no loss of correctness; post-processing below
# already normalizes to uppercase/alphanumeric-only, so the whitelist wasn't
# doing anything a whitelist-free read + normalize doesn't already do.

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def _read_with_psm(image: Image.Image, psm: int) -> tuple[str, float]:
    """Single OCR attempt at one PSM. Returns (normalized_text, confidence)."""
    data = pytesseract.image_to_data(
        image, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
    )
    words: list[str] = []
    confidences: list[float] = []
    for word, conf in zip(data["text"], data["conf"]):
        if not word.strip():
            continue
        words.append(word)
        conf_value = float(conf)
        if conf_value >= 0:  # tesseract uses -1 for "no confidence"
            confidences.append(conf_value)

    text = _NON_ALNUM_RE.sub("", "".join(words).upper())
    confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return text, confidence


def read_text(image: Image.Image) -> tuple[str, float]:
    """OCR a single plate crop, trying every PSM in CANDIDATE_PSMS.

    Returns the (normalized_text, confidence) of whichever PSM attempt
    produced non-empty text with the highest confidence. text is uppercase
    with all non-alphanumeric characters stripped. confidence is the mean
    word-level Tesseract confidence, mapped from 0-100 to 0-1. Returns
    ("", 0.0) if every PSM attempt came back empty.
    """
    # -1 sentinel (not 0.0): a valid attempt can legitimately score 0.0
    # confidence and must still beat "no attempt has found text yet".
    best_text, best_confidence = "", -1.0
    for psm in CANDIDATE_PSMS:
        text, confidence = _read_with_psm(image, psm)
        if text and confidence > best_confidence:
            best_text, best_confidence = text, confidence
    return (best_text, best_confidence) if best_text else ("", 0.0)


def _expected_plate(filename: str) -> str | None:
    """Pull an expected plate from a filename like 'WXY1234.jpg' or 'WXY1234_02.jpg'."""
    stem = Path(filename).stem.split("_")[0]
    candidate = _NON_ALNUM_RE.sub("", stem.upper())
    return candidate or None


def main(crops_dir: str) -> None:
    directory = Path(crops_dir)
    if not directory.is_dir():
        print(f"error: {crops_dir} is not a directory")
        sys.exit(1)

    image_paths = sorted(
        p for p in directory.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if not image_paths:
        print(f"error: no .jpg/.jpeg/.png files found in {crops_dir}")
        sys.exit(1)

    total_scored = 0
    correct = 0
    print(f"{'file':<30} {'read':<12} {'conf':>5}  expected")
    print("-" * 70)
    for path in image_paths:
        with Image.open(path) as img:
            text, confidence = read_text(img)
        expected = _expected_plate(path.name)
        marker = ""
        if expected:
            total_scored += 1
            is_match = text == expected
            correct += is_match
            marker = "OK" if is_match else f"expected {expected}"
        print(f"{path.name:<30} {text:<12} {confidence:>5.2f}  {marker}")

    if total_scored:
        print("-" * 70)
        print(f"accuracy: {correct}/{total_scored} ({100 * correct / total_scored:.0f}%)")
    else:
        print("\nno filenames encoded an expected plate — no accuracy computed.")
        print("rename crops like 'WXY1234.jpg' to score them.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python ocr_spike.py <crops_dir>")
        sys.exit(1)
    main(sys.argv[1])
