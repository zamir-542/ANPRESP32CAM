# PlateScope — Phone Server

The phone-side compute node: a Flask app that receives a captured JPEG,
**localizes the plate (OpenCV), reads it (Tesseract), and validates the
Malaysian format** (`pipeline.py`), logs the valid read, and serves a
dashboard of reads at `GET /`. A frame with no valid plate is reported as
`no_plate` and not logged (invariant #6 — never a bogus plate).

**LAN-only.** The server binds to `0.0.0.0:8000` so the ESP32 on the same WiFi can
reach it. Do not port-forward or tunnel it to the internet (invariant #4).

## Setup (Termux)

```sh
pkg update
pkg install python python-pillow python-numpy   # C-ext deps: pkg, NOT pip
pkg install tesseract               # OCR engine binary (Unit 04)
pkg install x11-repo                 # OpenCV is in the x11 repo, not main
pkg install opencv-python dbus       # cv2 (+ opencv, numpy) and the libdbus-1.so it loads
cd phone
pip install flask pytesseract       # pure Python — pip is fine
```

> **OpenCV on Termux is not obvious — steps verified on a Galaxy Note 8:**
> - It is **not** in the main repo (and not in TUR). It lives in **`x11-repo`**
>   — `pkg install x11-repo` first, then `pkg install opencv-python` (the
>   package is `opencv-python`, *not* `python-opencv`; it pulls in `opencv` +
>   `python-numpy`).
> - `import cv2` then fails with `libdbus-1.so not found` until you also
>   `pkg install dbus` (cv2's GUI backend links it; it isn't pulled in
>   automatically).
>
> **Do not `pip install pillow`/`opencv`/`numpy` on Termux** — pip compiles
> them from C source and fails. Use the prebuilt `pkg` builds above. Rule of
> thumb: C-extension package → `pkg install`; pure Python (flask, pytesseract)
> → `pip`.

Verify everything imports before running:

```sh
python -c "import flask, PIL, cv2, numpy, pytesseract; print('deps OK')"
tesseract --version
```

## Run

```sh
python app.py
```

On startup it creates `captures/` and `reads.db` if missing, then serves on
port 8000.

## Quick start (optional)

Typing `cd phone && python app.py` every session gets old fast — and Termux
loses its shell history (no ↑-arrow recall) if the app is swiped away instead
of exited cleanly. Set this up once:

```sh
cat >> ~/.bashrc << 'EOF'
shopt -s histappend
PROMPT_COMMAND="history -a;$PROMPT_COMMAND"
alias platescope='cd ~/ANPRESP32CAM/phone && python app.py'
EOF
source ~/.bashrc
```

(Adjust the path in the alias if you cloned the repo somewhere other than
`~/ANPRESP32CAM`.) The `histappend`/`PROMPT_COMMAND` lines save history after
every command instead of only on clean exit, so ↑-arrow recall survives a
swipe-close. After this, just run:

```sh
platescope
```

For a true one-tap launch from the Android home screen, install the
**Termux:Widget** add-on app and add a matching script at
`~/.shortcuts/platescope.sh` (same `cd` + `python app.py`, `chmod +x` it).

## Find the phone's LAN IP

Unit 02's firmware needs this IP in `firmware/secrets.h`.

- **Termux:** `ifconfig wlan0` (or `ip addr show wlan0`) → the `inet` address,
  e.g. `192.168.0.42`.
- **Android Settings:** Wi-Fi → the connected network → IP address.

The ESP32 will POST to `http://<that-ip>:8000/upload`.

## Quick test (from a PC on the same network)

```sh
curl -F "image=@plate.jpg" http://<phone-ip>:8000/upload
# valid plate  -> {"ok":true,"plate":"WXY1234","confidence":0.87}
# no plate     -> {"ok":false,"reason":"no_plate"}
```

Then open `http://<phone-ip>:8000/` in a browser — a valid read appears
newest-first (plate crop + text + confidence), auto-refreshing every 4 s.

## OCR accuracy harness (`ocr.py`)

`phone/ocr.py` holds `read_text(crop)` — the OCR step `pipeline.py` calls —
and doubles as a standalone accuracy harness (originally the Unit 04
Tesseract feasibility spike). To re-measure read accuracy on a folder of
crops, name each file with the plate it should read (`WXY1234.jpg`, or
`WXY1234_02.jpg` for a second sample of the same plate) and put them under
`phone/ocr_test_crops/` (gitignored — plate images are personal data, same
as `captures/`):

```sh
python ocr.py ocr_test_crops
```

Prints a per-crop read + confidence, and an overall accuracy line.

## Notes

- `captures/`, `reads.db`, and `ocr_test_crops/` hold captured imagery /
  plate data (personal data) and are gitignored — never commit them.
- Pin versions here once they settle (Flask, Pillow, pytesseract, OpenCV,
  numpy) for reproducibility.
