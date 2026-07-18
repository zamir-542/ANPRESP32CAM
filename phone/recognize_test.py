"""Batch pipeline harness: run the FULL recognizer on real frames and score.

Unlike ocr.py (which OCRs an already-tight crop), this runs the whole
pipeline — localize -> OCR -> validate — on every image in a folder, exactly
as a live capture would. It's the Unit 06 tuning tool: gather real full-frame
ESP32 captures, name each by the true plate (same convention as ocr.py: text
before the first '_', e.g. "BHV33.jpg" or "BHV33_02.jpg"), and this reports
per-frame what happened plus an overall accuracy — the data to tune the
pipeline.py thresholds against.

The `boxes` column shows how many candidate regions localization found, so a
miss is diagnosable at a glance: `boxes 0` means localization failed to find
the plate; `boxes >=1` with no/ wrong read points at OCR or the thresholds.

Usage:
    python recognize_test.py <frames_dir>

For full per-candidate detail (every read + why it was rejected), run with
PLATESCOPE_DEBUG=1 to get pipeline.py's stderr trace alongside the table.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

import pipeline
from ocr import _expected_plate


def main(frames_dir: str) -> None:
    directory = Path(frames_dir)
    if not directory.is_dir():
        print(f"error: {frames_dir} is not a directory")
        sys.exit(1)

    paths = sorted(
        p for p in directory.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if not paths:
        print(f"error: no .jpg/.jpeg/.png files found in {frames_dir}")
        sys.exit(1)

    total_scored = 0
    correct = 0
    print(f"{'file':<28} {'boxes':>5} {'read':<10} {'conf':>5}  verdict")
    print("-" * 72)
    for path in paths:
        raw = path.read_bytes()

        # Box count = localization visibility (recognize() doesn't expose it).
        bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        n_boxes = len(pipeline._localize(bgr)) if bgr is not None else 0

        result = pipeline.recognize(raw)
        read = result.plate or "-"
        expected = _expected_plate(path.name)
        if expected:
            total_scored += 1
            if result.plate == expected:
                correct += 1
                verdict = "OK"
            elif result.plate is None:
                verdict = f"no_plate (exp {expected})"
            else:
                verdict = f"WRONG (exp {expected})"
        else:
            verdict = "no_plate" if result.plate is None else ""
        print(f"{path.name:<28} {n_boxes:>5} {read:<10} {result.confidence:>5.2f}  {verdict}")

    if total_scored:
        print("-" * 72)
        print(f"accuracy: {correct}/{total_scored} ({100 * correct / total_scored:.0f}%)")
    else:
        print("\nno filenames encoded an expected plate — no accuracy computed.")
        print("name frames like 'BHV33.jpg' to score them.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python recognize_test.py <frames_dir>")
        sys.exit(1)
    main(sys.argv[1])
