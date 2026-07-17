# PlateScope — Phone Server

The phone-side compute node. In Unit 01 this is a Flask app that receives a JPEG
at `POST /upload`, saves it, logs a **stub** read (`TEST123`), and serves a
dashboard of reads at `GET /`. Real localization + OCR arrive in later units.

**LAN-only.** The server binds to `0.0.0.0:8000` so the ESP32 on the same WiFi can
reach it. Do not port-forward or tunnel it to the internet (invariant #4).

## Setup (Termux)

```sh
pkg update
pkg install python python-pillow    # Pillow must come from pkg, NOT pip
cd phone
pip install flask                   # pure Python — pip is fine
```

> **Do not `pip install pillow` on Termux** — pip tries to compile it from C
> source and fails with *"Failed building wheel for pillow"*. Termux ships a
> prebuilt `python-pillow`; install that with `pkg` instead. Rule of thumb on
> Termux: anything with a C extension → `pkg install`; pure Python → `pip`.

Verify both import before running:

```sh
python -c "import flask, PIL; print('flask + pillow OK', PIL.__version__)"
```

(OpenCV is deliberately deferred to Unit 05; when it arrives it's
`pkg install python-opencv`, again not pip.)

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
curl -F "image=@sample.jpg" http://<phone-ip>:8000/upload
# -> {"ok":true,"plate":"TEST123","confidence":1.0}
```

Then open `http://<phone-ip>:8000/` in a browser — the capture appears
newest-first, auto-refreshing every 3 seconds.

## Unit 04 — OCR spike

Standalone feasibility check for `phone/ocr_spike.py` — not wired into
`app.py` yet (that's Unit 05). Proves Tesseract runs in Termux and measures
its raw read accuracy on real plate crops.

```sh
pkg install tesseract        # the OCR binary — pkg, not pip
pip install pytesseract      # pure Python wrapper — pip is fine
```

Verify the binary installed:

```sh
tesseract --version
```

Gather a handful of real plate crops (e.g. cropped by hand from Unit 03
captures) into a folder, naming each file with the plate it should read —
`WXY1234.jpg`, or `WXY1234_02.jpg` for a second sample of the same plate.
Put them under `phone/ocr_test_crops/` (gitignored — plate images are
personal data, same as `captures/`).

```sh
python ocr_spike.py ocr_test_crops
```

Prints a per-crop read + confidence, and an overall accuracy line. Record the
result in `context/progress-tracker.md` along with the go/no-go call: keep
Tesseract, or escalate to EasyOCR/PaddleOCR-ONNX per the build plan.

## Notes

- `captures/`, `reads.db`, and `ocr_test_crops/` hold captured imagery /
  plate data (personal data) and are gitignored — never commit them.
- Pin versions here once they settle (Flask, Pillow, pytesseract) for
  reproducibility.
