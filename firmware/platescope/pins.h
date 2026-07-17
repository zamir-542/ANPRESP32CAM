// pins.h — PlateScope single source of hardware truth (invariant #1).
//
// Every GPIO number and every hardware timing constant used by the firmware
// is declared here. No other file may contain a raw pin number or a magic
// hardware constant.
//
// NOTE: AP_SSID / AP_PASSWORD are Wi-Fi credentials, not hardware constants —
// they're defined directly in platescope.ino (edit them there before flashing).
//
// Reference: context/interface-context.md § Hardware / Embedded (ESP32-CAM)

#pragma once
#include <cstdint>

// ── On-board status LED ──────────────────────────────────────────────────────
// GPIO 33, active LOW (LED_ON = LOW, LED_OFF = HIGH).
constexpr uint8_t STATUS_LED_PIN = 33;
constexpr uint8_t LED_ON = LOW;
constexpr uint8_t LED_OFF = HIGH;

// ── Flash LED ────────────────────────────────────────────────────────────────
// GPIO 4, active HIGH.  Fired briefly at capture; must always end OFF.
constexpr uint8_t FLASH_LED_PIN = 4;

// ── Camera (AI-Thinker OV2640) — fixed mapping, do NOT reassign ──────────────
// GPIO 0 (XCLK) was the Unit 02 BOOT button; it is now camera-owned, which is
// why the physical-button trigger was removed in Unit 03.
constexpr int PWDN_GPIO_NUM  = 32;
constexpr int RESET_GPIO_NUM = -1;   // not wired
constexpr int XCLK_GPIO_NUM  =  0;
constexpr int SIOD_GPIO_NUM  = 26;
constexpr int SIOC_GPIO_NUM  = 27;
constexpr int Y9_GPIO_NUM    = 35;
constexpr int Y8_GPIO_NUM    = 34;
constexpr int Y7_GPIO_NUM    = 39;
constexpr int Y6_GPIO_NUM    = 36;
constexpr int Y5_GPIO_NUM    = 21;
constexpr int Y4_GPIO_NUM    = 19;
constexpr int Y3_GPIO_NUM    = 18;
constexpr int Y2_GPIO_NUM    =  5;
constexpr int VSYNC_GPIO_NUM = 25;
constexpr int HREF_GPIO_NUM  = 23;
constexpr int PCLK_GPIO_NUM  = 22;

// ── Camera capture settings (tunable in Unit 06) ────────────────────────────
// XCLK at 10 MHz (not 20): the widely-known fix for corrupted / bottom-black
// JPEGs on AI-Thinker clone boards. Slower frame rate — irrelevant for
// single-shot capture.
constexpr uint32_t XCLK_FREQ_HZ    = 10000000;  // 10 MHz camera master clock
constexpr int      JPEG_QUALITY    = 12;         // 10–63; lower = better/larger
constexpr uint32_t FLASH_SETTLE_MS = 120;        // flash on → let exposure settle
constexpr uint8_t  CAPTURE_RETRIES = 3;          // re-grab if frame looks corrupt
constexpr uint16_t CAM_HTTP_PORT   = 80;         // ESP32 capture web server port

// ── SoftAP tuning ────────────────────────────────────────────────────────────
// Fixed Wi-Fi channel for the AP. In RF-noisy places (campus networks) the
// default channel is often congested; 6 is a reasonable mid-band pick. If
// drops persist, try 1 or 11 — only these three don't overlap.
constexpr uint8_t AP_CHANNEL = 6;

// ── Status-LED blink timing ──────────────────────────────────────────────────
constexpr uint32_t BLINK_SHORT_MS = 150; // Duration of a short LED pulse
constexpr uint32_t BLINK_GAP_MS = 80;    // Gap between pulses in a multi-blink

// ── Serial ───────────────────────────────────────────────────────────────────
constexpr uint32_t SERIAL_BAUD = 115200;
