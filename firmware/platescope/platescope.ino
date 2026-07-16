// platescope.ino — Unit 03: Camera Capture (SoftAP + pull)
//
// The ESP32 hosts its own Wi-Fi access point (SoftAP) AND a small web server.
// The phone joins the AP and pulls a photo on demand:
//
//   phone  --GET http://192.168.4.1/capture-->  ESP32
//   ESP32  fires flash, grabs one OV2640 JPEG, returns it (image/jpeg)
//
// There is NO physical button in this unit: GPIO 0 is the camera's XCLK clock,
// so the Unit 02 BOOT-button trigger was removed. The phone dashboard's
// "Capture" button is the trigger now.
//
// Invariants upheld:
//   #1 — all GPIO numbers are in pins.h, none appear here.
//   #3 — AP credentials + phone IP live in secrets.h (gitignored).
//   #4 — self-contained LAN over the ESP32's own AP; no cloud.

#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "pins.h"
#include "secrets.h"

WebServer server(CAM_HTTP_PORT);

// ── Forward declarations ─────────────────────────────────────────────────────
static void startAP();
static bool initCamera();
static void handleCapture();
static void blinkOk();
static void blinkErr();

// ── LED helpers ──────────────────────────────────────────────────────────────

static void ledInit() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LED_OFF);  // known-safe state on boot
}

static void blinkOk() {
  digitalWrite(STATUS_LED_PIN, LED_ON);
  delay(BLINK_SHORT_MS);
  digitalWrite(STATUS_LED_PIN, LED_OFF);
}

static void blinkErr() {
  for (uint8_t i = 0; i < 2; i++) {
    digitalWrite(STATUS_LED_PIN, LED_ON);
    delay(BLINK_SHORT_MS);
    digitalWrite(STATUS_LED_PIN, LED_OFF);
    if (i == 0) delay(BLINK_GAP_MS);
  }
  digitalWrite(STATUS_LED_PIN, LED_OFF);
}

// Guarantee the flash LED is off. Called on every capture exit path.
static void flashOff() {
  digitalWrite(FLASH_LED_PIN, LOW);
}

// ── Wi-Fi (SoftAP) ───────────────────────────────────────────────────────────

// Bring up the device's own access point. The phone joins this SSID; there is
// no router or internet involved. The ESP32 is the gateway at 192.168.4.1.
//
// Diagnostic: log every station join/leave. If serial shows "station left"
// right before a failed capture, the phone is dropping off the AP (Android
// power-save / roaming) — the problem is not the ESP32.
static void onWifiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      Serial.println("[WIFI] station joined the AP");
      break;
    case ARDUINO_EVENT_WIFI_AP_STADISCONNECTED:
      Serial.println("[WIFI] station LEFT the AP");
      break;
    default:
      break;
  }
}

static void startAP() {
  Serial.println("[WIFI] starting access point ...");
  WiFi.mode(WIFI_AP);
  WiFi.onEvent(onWifiEvent);
  WiFi.setSleep(false);  // no modem power-save: fewer latency spikes/drops

  if (WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL)) {
    Serial.print("[WIFI] AP up — SSID \"");
    Serial.print(AP_SSID);
    Serial.print("\", channel ");
    Serial.print(AP_CHANNEL);
    Serial.print(", gateway ");
    Serial.println(WiFi.softAPIP());              // 192.168.4.1 by default
  } else {
    Serial.println("[ERR] AP start failed");
  }
}

// ── Camera ───────────────────────────────────────────────────────────────────

static bool initCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = XCLK_FREQ_HZ;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_SVGA;           // 800×600 start (tunable, Unit 06)
  config.jpeg_quality = JPEG_QUALITY;
  config.fb_count     = 2;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERR] camera init 0x%x\n", err);
    return false;
  }
  Serial.println("[CAM] init ok");
  return true;
}

// A valid JPEG ends with the EOI marker FF D9. A frame that doesn't is
// corrupt (the classic "bottom of the photo is black" symptom) — reject it
// on-device instead of shipping garbage to the phone.
static bool frameLooksComplete(const camera_fb_t* fb) {
  return fb && fb->len > 2 &&
         fb->buf[fb->len - 2] == 0xFF && fb->buf[fb->len - 1] == 0xD9;
}

// GET /capture — fire the flash, grab one JPEG frame, return it as image/jpeg.
static void handleCapture() {
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(FLASH_SETTLE_MS);

  // Warm-up: discard one frame so we don't serve a stale pre-flash buffer.
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb) {
    esp_camera_fb_return(fb);
    fb = nullptr;
  }

  // Grab, verifying integrity; retry a corrupt frame.
  for (uint8_t attempt = 0; attempt < CAPTURE_RETRIES; attempt++) {
    fb = esp_camera_fb_get();
    if (frameLooksComplete(fb)) break;
    Serial.printf("[CAM] corrupt/empty frame (attempt %u) — retrying\n", attempt + 1);
    if (fb) {
      esp_camera_fb_return(fb);
      fb = nullptr;
    }
  }

  if (!fb) {
    flashOff();
    Serial.println("[ERR] capture failed (no complete frame)");
    server.send(500, "text/plain", "capture failed");
    blinkErr();
    return;
  }

  Serial.printf("[CAM] captured %u bytes\n", (unsigned) fb->len);
  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  server.sendContent((const char*) fb->buf, fb->len);

  esp_camera_fb_return(fb);
  flashOff();
  blinkOk();
}

// ── Arduino entry points ──────────────────────────────────────────────────────

void setup() {
  Serial.begin(SERIAL_BAUD);
  Serial.println();
  Serial.println("PlateScope — Unit 03: camera capture (SoftAP + pull)");

  ledInit();

  pinMode(FLASH_LED_PIN, OUTPUT);
  flashOff();  // flash off until a capture fires it

  startAP();

  if (!initCamera()) {
    Serial.println("[ERR] halting — camera init failed");
    blinkErr();
    // Fall through: the AP + server still come up so the failure is visible,
    // but /capture will return 500 until the camera is fixed.
  }

  server.on("/capture", HTTP_GET, handleCapture);
  server.begin();
  Serial.println("[HTTP] capture server on http://192.168.4.1/capture");
  Serial.println("[SYS] ready — connect the phone to the AP and tap Capture");
}

void loop() {
  server.handleClient();
}
