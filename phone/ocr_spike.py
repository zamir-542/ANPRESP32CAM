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

# --- Tunables (single source of truth for this spike) ----------------------
# --psm 7: treat the crop as a single line of text (plates are one line).
# Whitelisting A-Z0-9 measurably helps accuracy on short strings with no
# lowercase/punctuation.
TESSERACT_CONFIG = (
    "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def read_text(image: Image.Image) -> tuple[str, float]:
    """OCR a single plate crop.

    Returns (normalized_text, confidence). text is uppercase with all
    non-alphanumeric characters stripped. confidence is the mean word-level
    Tesseract confidence, mapped from its native 0-100 scale to 0-1; 0.0 if
    nothing was detected.
    """
    data = pytesseract.image_to_data(
        image, config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT
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
