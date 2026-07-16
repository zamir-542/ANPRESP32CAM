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

## Notes

- `captures/` and `reads.db` hold captured imagery / plate data (personal data)
  and are gitignored — never commit them.
- Pin versions here once they settle (Flask, Pillow) for reproducibility.
