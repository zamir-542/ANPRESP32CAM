# PlateScope — Distributed-Edge Malaysian ANPR

## Overview

PlateScope is a portfolio piece that demonstrates a real **edge AI** application:
automatic number-plate recognition (ANPR) for **Malaysian plates**, built as a
**distributed edge** system across two cheap devices. An AI-Thinker ESP32-CAM is
the *sensor* — press its BOOT button and it fires a flash and captures one frame.
A phone is the *compute* — it runs a small Python program (in Termux) that
localizes the plate, reads it with OCR, validates it against the Malaysian plate
format, and logs the result to a web page it serves on the local WiFi. The whole
system is **fully offline / LAN-only** — no cloud, no internet. The "edge" story
is the point: capture happens on a $8 microcontroller, recognition happens
on-device on the phone, and nothing ever leaves the local network.

## Goals

1. A working end-to-end demo: press BOOT → within a few seconds a correctly
   decoded Malaysian plate appears on the phone-served dashboard, with the plate
   crop and a timestamp.
2. A clean, honest **distributed-edge architecture** with one well-defined
   ESP32↔phone contract — a portfolio-legible boundary between "capture" and
   "compute".
3. Fully offline operation: the core flow works with only the ESP32 and the phone
   on the same WiFi, no internet reachable.

## Core Flow

1. Power on the ESP32-CAM; it joins the local WiFi.
2. Press the BOOT button.
3. Firmware fires the flash LED and captures one JPEG from the OV2640 sensor.
4. Firmware `POST`s the JPEG over WiFi to the phone's Flask endpoint
   (`POST /upload`).
5. The phone pipeline decodes the JPEG → OpenCV localizes candidate plate
   region(s) → OCR reads each crop → the text is validated against the Malaysian
   plate pattern → the best valid plate wins.
6. The read (crop thumbnail + decoded plate + confidence + timestamp) is appended
   to a local log; the crop is saved to disk.
7. The phone serves a dashboard at `GET /` showing the reads newest-first; you
   view it in a browser on the same WiFi and screenshot it for the portfolio.

## Features

### Capture (ESP32-CAM)

- Single-shot, button-triggered capture (no continuous video).
- Flash LED fired at capture for consistent lighting.
- JPEG upload to the phone over the LAN.

### Compute (phone, Python in Termux)

- Classical OpenCV plate localization (no trained model in v1).
- OCR of the localized crop.
- Malaysian-format validation — garbage that doesn't match the pattern is
  rejected rather than reported.

### Output (phone-served web dashboard)

- Newest-first log of reads: crop thumbnail + plate text + confidence + timestamp.
- Auto-refreshing, mobile-first page served on the LAN.

## Scope

### In Scope

- ESP32-CAM firmware: WiFi, BOOT-triggered flash-lit capture, JPEG upload.
- Phone app: Flask upload endpoint + dashboard, OpenCV localization, OCR,
  Malaysian-format validation, local logging.
- Single Malaysian plate per frame, common Peninsular format.
- Own/consenting vehicles only; blurred plates in any published screenshot.

### Out of Scope

- Real-time / continuous video detection (single-shot only).
- Multiple plates per frame.
- Vehicle-owner / database lookup.
- Gate/barrier actuation or any physical control output.
- Cloud sync or remote (internet) access — LAN-only.
- A trained detector or trained OCR model (classical CV + off-the-shelf OCR only
  in v1).
- Robust coverage of every Malaysian series (Sabah/Sarawak, diplomatic, military,
  vanity) — v1 targets the common Peninsular format.

## Success Criteria

1. Pressing BOOT captures a flash-lit frame, uploads it, and a correctly decoded
   plate for a known consenting vehicle appears on the dashboard within a few
   seconds — one clean end-to-end demo.
2. The system runs entirely on the ESP32 + phone over the LAN, with no internet
   reachable, and still works.
3. A string that does not match the Malaysian plate pattern is reported as
   "no valid plate found", never as a confident plate.
