/*
 * NOVA - MCU firmware (runs on the STM32U585 / Arduino Core for Zephyr
 * side of the UNO Q, FQBN arduino:zephyr:unoq)
 * ---------------------------------------------------------------------
 * Responsibilities of this half of the app (real-time / hardware):
 *   - Drive the two GC9A01 round "eye" displays via NovaEyes, blitting
 *     the team's own pre-rendered emotion bitmaps (no LovyanGFX -- see
 *     NovaEyes.h and README for why).
 *   - Drive the head-tracking servo motor.
 *   - Expose both of the above to the Python (MPU/Linux) side over the
 *     Arduino Bridge (Arduino_RouterBridge), so all the heavy lifting
 *     (camera, emotion CNN, Whisper STT, the LLM, TTS, IoT/MQTT, music,
 *     SOS calling) can live in Python where the actual libraries exist.
 *
 * Bridge functions exposed to Python (see python/bridge_client.py):
 *   set_eye_state(int eyeState)      -- change eye expression (NovaEyeState)
 *   trigger_blink()                  -- one-off blink animation
 *   set_head_angle(int angleDeg)     -- move head servo (0-180)
 *   get_head_angle() -> int          -- current servo angle
 *
 * Wiring:
 *   Eyes (shared bus): SCK D13, MOSI D11, DC D5, RST D4, CS_L D9, CS_R D10
 *   Head servo signal: D6  (5V/PWM-capable pin -- pick any free digital
 *                           pin on your build; D6 avoids the eye-bus pins)
 *
 * Status: implementation complete, pending compilation and on-hardware
 * verification against the arduino:zephyr toolchain (board "Arduino UNO
 * Q" in Arduino IDE 2.x or App Lab). Verify servo range and eye
 * rendering timing on the physical build before relying on it live.
 * ---------------------------------------------------------------------
 */

#include <Arduino_RouterBridge.h>
#include <Servo.h>
#include "NovaEyes.h"

// ── Pins ──────────────────────────────────────────────────────────────
#define PIN_RST   4
#define PIN_DC    5
#define PIN_CS_L  9
#define PIN_CS_R  10
#define PIN_SERVO 6

NovaEyes eyes(PIN_RST, PIN_DC, PIN_CS_L, PIN_CS_R);
Servo headServo;

// ── Servo smoothing state ────────────────────────────────────────────
volatile int targetAngle  = 90;   // requested angle from Python
int currentAngle          = 90;   // angle actually written to the servo
unsigned long lastServoStepMs = 0;
const unsigned long SERVO_STEP_INTERVAL_MS = 15; // ~ one degree per 15ms
const int SERVO_MIN_ANGLE = 20;   // mechanical safety limits -- adjust to
const int SERVO_MAX_ANGLE = 160;  // your actual head/servo range before demo

// ═══════════════════════════════════════════════════════════════════════
//  Functions exposed to Python over the Bridge
// ═══════════════════════════════════════════════════════════════════════

void set_eye_state(int eyeState) {
  eyes.setState(eyeState);
}

void trigger_blink() {
  eyes.blink();
}

void set_head_angle(int angleDeg) {
  if (angleDeg < SERVO_MIN_ANGLE) angleDeg = SERVO_MIN_ANGLE;
  if (angleDeg > SERVO_MAX_ANGLE) angleDeg = SERVO_MAX_ANGLE;
  targetAngle = angleDeg;
}

int get_head_angle() {
  return currentAngle;
}

// ═══════════════════════════════════════════════════════════════════════
//  Setup & loop
// ═══════════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);

  eyes.begin();

  headServo.attach(PIN_SERVO);
  headServo.write(currentAngle);

  Bridge.begin();
  Bridge.provide("set_eye_state", set_eye_state);
  Bridge.provide("trigger_blink", trigger_blink);
  Bridge.provide("set_head_angle", set_head_angle);
  Bridge.provide("get_head_angle", get_head_angle);
}

void loop() {
  Bridge.update();
  eyes.update(); // handles automatic idle blinking

  // Non-blocking, gradual servo motion so head turns look natural instead
  // of snapping instantly to the tracked face position.
  unsigned long now = millis();
  if (now - lastServoStepMs >= SERVO_STEP_INTERVAL_MS) {
    lastServoStepMs = now;
    if (currentAngle < targetAngle) {
      currentAngle++;
      headServo.write(currentAngle);
    } else if (currentAngle > targetAngle) {
      currentAngle--;
      headServo.write(currentAngle);
    }
  }
}
