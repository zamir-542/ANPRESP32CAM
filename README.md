# PlateScope — Distributed-Edge Malaysian ANPR

An ESP32-CAM and a phone, working together, fully offline. Press the ESP32's
BOOT button → it fires a flash and grabs one frame → the photo goes to a
phone over WiFi → the phone localizes the plate, reads it with OCR, checks it
against the Malaysian plate format, and logs the result to a dashboard it
serves on the local network. No cloud, no internet, no gate/database lookup —
just a clean, portfolio-legible "capture at the edge, recognize on-device"
demo.

## How it works

```
[ESP32-CAM]  --BOOT press-->  flash + capture (OV2640)
     |
     |  hosts its own WiFi AP (SoftAP, 192.168.4.1)
     v
[Phone, Termux]  joins the AP  -->  pulls the photo
     |
     |  OpenCV localization -> OCR -> Malaysian-format validation
     v
  dashboard served on the LAN (plate + crop + timestamp, newest-first)
```

- **Capture** — `firmware/`: Arduino C++ sketch for an AI-Thinker ESP32-CAM.
  Hosts its own WiFi access point (no router or internet needed) and serves a
  flash-lit JPEG capture endpoint.
- **Compute** — `phone/`: a Flask app run in Termux. Pulls the photo from the
  ESP32, runs OpenCV plate localization + OCR, validates the result against
  the Malaysian plate pattern, and serves a mobile-first dashboard.

## Status

Camera capture is working end-to-end on real hardware: button press → flash
→ photo → dashboard. OCR and plate validation are the next milestone.

## Getting started

1. **Firmware** — flash the ESP32-CAM. See [`firmware/README.md`](firmware/README.md).
2. **Phone** — run the Flask server in Termux. See [`phone/README.md`](phone/README.md).
3. Join the phone to the ESP32's WiFi AP, open the dashboard, tap **Capture**.

## Project layout

```
firmware/    ESP32-CAM sketch (Arduino C++) — WiFi AP, flash-lit capture
phone/       Flask app (Python, runs in Termux) — pull, recognize, dashboard
```

## Design constraints

- **Fully offline** — the core capture → recognize → serve flow never
  depends on the internet or a cloud service.
- **Single plate per frame, common Peninsular Malaysian format** — no
  multi-plate detection, no Sabah/Sarawak/diplomatic/vanity coverage in v1.
- **No confident guesses** — a string that fails Malaysian-format validation
  is reported as "no plate found," never surfaced as a plate.
- **Own/consenting vehicles only** — plates are blurred/redacted in any
  published screenshot or GIF.

## License

_Add a license if you want this repo to be reusable by others._
