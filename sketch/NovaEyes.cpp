/*
 * NovaEyes.cpp
 * See NovaEyes.h for design notes (why no LovyanGFX, wiring, flash budget).
 */

#include "NovaEyes.h"
#include <SPI.h>

// ── Team-rendered emotion bitmaps (240x240 RGB565, PROGMEM) ─────────────
#include "normal_open_centre.h"
#include "normal_close_centre.h"
#include "normal_open_left_looking.h"
#include "normal_open_right_looking.h"
#include "happy_open_left.h"
#include "happy_close_left.h"
#include "angry_open_left.h"

// ── Aliases matched to the real array names inside each .h file ────────
// (Same aliasing the team used in their ESP32/LovyanGFX prototype.)
#define IMG_NEUTRAL_CENTRE_OPEN   normal_centre_eye_data
#define IMG_NEUTRAL_CENTRE_CLOSE  normal_centre_left_eye_data
#define IMG_NEUTRAL_LOOK_LEFT     normal_left_eye_data
#define IMG_NEUTRAL_LOOK_RIGHT    normal_right_eye_data
#define IMG_HAPPY_OPEN            happy_left_1_data
#define IMG_HAPPY_CLOSE           happy_left_2_data
// NOTE: angry_open_left.h's internal array is named sad_right_eye_data
// (a leftover from the source file's original name) -- it is in fact the
// "angry, eye open" render. Re-render/rename if this ever looks wrong.
#define IMG_ANGRY_OPEN            sad_right_eye_data

static const int16_t SCREEN_W = 240;
static const int16_t SCREEN_H = 240;

// One scratch row buffer, reused for whichever mirrored blit is running.
static uint16_t rowBuf[SCREEN_W];

NovaEyes::NovaEyes(uint8_t pinRst, uint8_t pinDc, uint8_t pinCsLeft, uint8_t pinCsRight)
  : _rst(pinRst), _dc(pinDc), _csL(pinCsLeft), _csR(pinCsRight) {}

// ── Public API ───────────────────────────────────────────────────────────

void NovaEyes::begin() {
  pinMode(_rst, OUTPUT);
  pinMode(_dc,  OUTPUT);
  pinMode(_csL, OUTPUT);
  pinMode(_csR, OUTPUT);

  digitalWrite(_csL, HIGH);
  digitalWrite(_csR, HIGH);
  digitalWrite(_dc,  HIGH);

  // Shared hardware reset line for both panels
  digitalWrite(_rst, LOW);  delay(20);
  digitalWrite(_rst, HIGH); delay(120);

  SPI.begin();
  SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));

  gc9a01Init(_csL);
  gc9a01Init(_csR);

  setState(EYE_NEUTRAL_CENTRE, true);
  _nextIdleBlinkAt = millis() + 4000;
}

// ── Emotion -> image pair + mirror rule ─────────────────────────────────
// This table reproduces the team's ESP32 prototype exactly:
//   - neutral (centre/left/right-looking): same image on both eyes, no mirror
//   - happy / angry: left eye direct, right eye mirrored
//   - sad (placeholder, reuses the angry-open art): left eye mirrored,
//     right eye direct -- i.e. the mirror side is flipped relative to
//     happy/angry, matching the prototype's blinkMirroredLeft() call.

NovaEyes::EyeImageSet NovaEyes::imagesForState(int eyeState) const {
  switch (eyeState) {
    case EYE_NEUTRAL_LOOK_LEFT:
      return { IMG_NEUTRAL_LOOK_LEFT, IMG_NEUTRAL_CENTRE_CLOSE, MIRROR_NONE };

    case EYE_NEUTRAL_LOOK_RIGHT:
      return { IMG_NEUTRAL_LOOK_RIGHT, IMG_NEUTRAL_CENTRE_CLOSE, MIRROR_NONE };

    case EYE_HAPPY:
      return { IMG_HAPPY_OPEN, IMG_HAPPY_CLOSE, MIRROR_RIGHT };

    case EYE_ANGRY:
      return { IMG_ANGRY_OPEN, IMG_NEUTRAL_CENTRE_CLOSE, MIRROR_RIGHT };

    case EYE_SAD:
      // Placeholder until a dedicated sad_*.h pair exists (see header note).
      return { IMG_ANGRY_OPEN, IMG_NEUTRAL_CENTRE_CLOSE, MIRROR_LEFT };

    case EYE_NEUTRAL_CENTRE:
    default:
      return { IMG_NEUTRAL_CENTRE_OPEN, IMG_NEUTRAL_CENTRE_CLOSE, MIRROR_NONE };
  }
}

void NovaEyes::setState(int eyeState, bool force) {
  if (!force && eyeState == _currentState) return;
  _currentState = eyeState;
  EyeImageSet set = imagesForState(eyeState);
  showImages(set.openImage, set.mirror);
}

void NovaEyes::blink() {
  EyeImageSet set = imagesForState(_currentState);

  showImages(set.closeImage, set.mirror);
  delay(100); // matches the ~100ms "closeMs" timing validated on the prototype

  showImages(set.openImage, set.mirror);

  _nextIdleBlinkAt = millis() + 3000 + (millis() % 3000); // pseudo-random 3-6s
}

void NovaEyes::update() {
  if (millis() >= _nextIdleBlinkAt) {
    blink();
  }
}

// ── Rendering ────────────────────────────────────────────────────────────

void NovaEyes::showImages(const uint16_t *img, MirrorMode mirror) {
  switch (mirror) {
    case MIRROR_RIGHT:
      pushImage(_csL, img);
      pushImageMirrored(_csR, img);
      break;
    case MIRROR_LEFT:
      pushImageMirrored(_csL, img);
      pushImage(_csR, img);
      break;
    case MIRROR_NONE:
    default:
      pushImage(_csL, img);
      pushImage(_csR, img);
      break;
  }
}

void NovaEyes::pushImage(uint8_t cs, const uint16_t *img) {
  setWindow(cs, 0, 0, SCREEN_W - 1, SCREEN_H - 1);
  csSelect(cs);
  dcData();

  for (uint32_t i = 0; i < (uint32_t)SCREEN_W * SCREEN_H; i++) {
    uint16_t px = pgm_read_word(&img[i]);
    SPI.transfer(px >> 8);
    SPI.transfer(px & 0xFF);
  }

  csDeselect(cs);
}

void NovaEyes::pushImageMirrored(uint8_t cs, const uint16_t *img) {
  setWindow(cs, 0, 0, SCREEN_W - 1, SCREEN_H - 1);
  csSelect(cs);
  dcData();

  for (int16_t y = 0; y < SCREEN_H; y++) {
    const uint16_t *row = img + (uint32_t)y * SCREEN_W;
    for (int16_t x = 0; x < SCREEN_W; x++) {
      rowBuf[x] = pgm_read_word(&row[SCREEN_W - 1 - x]);
    }
    for (int16_t x = 0; x < SCREEN_W; x++) {
      SPI.transfer(rowBuf[x] >> 8);
      SPI.transfer(rowBuf[x] & 0xFF);
    }
  }

  csDeselect(cs);
}

// ── Low-level GC9A01 register driver (unchanged from the direct-SPI
//    approach validated in the team's original single-file prototype) ──

void NovaEyes::csSelect(uint8_t cs)   { digitalWrite(cs, LOW); }
void NovaEyes::csDeselect(uint8_t cs) { digitalWrite(cs, HIGH); }
void NovaEyes::dcCmd()  { digitalWrite(_dc, LOW); }
void NovaEyes::dcData() { digitalWrite(_dc, HIGH); }

void NovaEyes::writeCmd(uint8_t cs, uint8_t cmd) {
  csSelect(cs);
  dcCmd();
  SPI.transfer(cmd);
  csDeselect(cs);
}

void NovaEyes::writeCmdData(uint8_t cs, uint8_t cmd, const uint8_t *data, size_t len) {
  csSelect(cs);
  dcCmd();
  SPI.transfer(cmd);
  dcData();
  for (size_t i = 0; i < len; i++) SPI.transfer(data[i]);
  csDeselect(cs);
}

void NovaEyes::setWindow(uint8_t cs, uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
  { uint8_t d[] = {(uint8_t)(x0 >> 8), (uint8_t)x0, (uint8_t)(x1 >> 8), (uint8_t)x1};
    writeCmdData(cs, 0x2A, d, 4); }
  { uint8_t d[] = {(uint8_t)(y0 >> 8), (uint8_t)y0, (uint8_t)(y1 >> 8), (uint8_t)y1};
    writeCmdData(cs, 0x2B, d, 4); }
  writeCmd(cs, 0x2C); // memory write
}

void NovaEyes::gc9a01Init(uint8_t cs) {
  writeCmd(cs, 0xEF);
  { uint8_t d[] = {0xEB}; writeCmdData(cs, 0xEB, d, 1); }
  writeCmd(cs, 0xFE);
  writeCmd(cs, 0xEF);
  { uint8_t d[] = {0x14}; writeCmdData(cs, 0xEB, d, 1); }
  { uint8_t d[] = {0x40}; writeCmdData(cs, 0x84, d, 1); }
  { uint8_t d[] = {0xFF}; writeCmdData(cs, 0x85, d, 1); }
  { uint8_t d[] = {0xFF}; writeCmdData(cs, 0x86, d, 1); }
  { uint8_t d[] = {0xFF}; writeCmdData(cs, 0x87, d, 1); }
  { uint8_t d[] = {0x0A}; writeCmdData(cs, 0x88, d, 1); }
  { uint8_t d[] = {0x21}; writeCmdData(cs, 0x8A, d, 1); }
  { uint8_t d[] = {0x18}; writeCmdData(cs, 0x8B, d, 1); }
  { uint8_t d[] = {0x78}; writeCmdData(cs, 0x8C, d, 1); }
  { uint8_t d[] = {0x78}; writeCmdData(cs, 0x8D, d, 1); }
  { uint8_t d[] = {0x78}; writeCmdData(cs, 0x8E, d, 1); }
  { uint8_t d[] = {0x78}; writeCmdData(cs, 0x8F, d, 1); }
  { uint8_t d[] = {0x00, 0x00}; writeCmdData(cs, 0xB6, d, 2); }
  { uint8_t d[] = {0x08}; writeCmdData(cs, 0x36, d, 1); }  // MX/MY/MV/BGR
  { uint8_t d[] = {0x05}; writeCmdData(cs, 0x3A, d, 1); }  // 16-bit color
  { uint8_t d[] = {0x08, 0x08, 0x08, 0x08}; writeCmdData(cs, 0x90, d, 4); }
  { uint8_t d[] = {0x00}; writeCmdData(cs, 0xBD, d, 1); }
  { uint8_t d[] = {0x00}; writeCmdData(cs, 0xBC, d, 1); }
  { uint8_t d[] = {0x00, 0xB4, 0x00}; writeCmdData(cs, 0xFF, d, 3); }
  { uint8_t d[] = {0x80}; writeCmdData(cs, 0xC3, d, 1); }
  { uint8_t d[] = {0x80}; writeCmdData(cs, 0xC4, d, 1); }
  { uint8_t d[] = {0x77}; writeCmdData(cs, 0xC9, d, 1); }
  { uint8_t d[] = {0xFF}; writeCmdData(cs, 0xBE, d, 1); }
  { uint8_t d[] = {0x20}; writeCmdData(cs, 0xE1, d, 1); }
  { uint8_t d[] = {0x00, 0x00}; writeCmdData(cs, 0xE0, d, 2); }
  { uint8_t d[] = {0xD0, 0x08, 0x11, 0x08, 0x08, 0x04, 0x35, 0x33, 0x47, 0x17, 0x00, 0x00, 0x2B, 0x34};
    writeCmdData(cs, 0xE0, d, 14); } // positive gamma
  { uint8_t d[] = {0xD0, 0x08, 0x10, 0x08, 0x06, 0x06, 0x39, 0x44, 0x51, 0x0B, 0x16, 0x14, 0x2F, 0x31};
    writeCmdData(cs, 0xE1, d, 14); } // negative gamma
  writeCmd(cs, 0x21); // display inversion ON (required for GC9A01)
  writeCmd(cs, 0x11); // sleep out
  delay(120);
  writeCmd(cs, 0x29); // display on
  delay(20);
}
