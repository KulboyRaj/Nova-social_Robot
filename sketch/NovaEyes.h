/*
 * NovaEyes.h
 * ---------------------------------------------------------------------
 * Drives NOVA's two 1.28" round GC9A01 SPI displays ("eyes") using the
 * team's own pre-rendered emotion bitmaps (normal_open_centre.h,
 * normal_open_left_looking.h, normal_open_right_looking.h,
 * happy_open_left.h / happy_close_left.h, angry_open_left.h,
 * normal_close_centre.h), instead of procedurally-drawn shapes.
 *
 * No LovyanGFX is used. UNO Q's microcontroller runs Arduino Core for
 * Zephyr on an STM32U585, a different architecture from ESP32/RP2040.
 * LovyanGFX's library.properties only declares those architectures, and
 * its fast-path SPI/DMA code calls ESP-IDF-specific APIs that don't
 * exist under Zephyr, so it isn't available for this board regardless
 * of install method. This driver instead talks to the GC9A01 controller
 * directly over the standard SPI.h API (part of arduino:zephyr) and
 * blits full-frame RGB565 bitmaps from PROGMEM, exactly the way the
 * team's ESP32/LovyanGFX prototype (BlinkingHumanEye.ino) did with
 * pushImage()/a manual mirrored-row blit -- the pixel data, the mirror
 * rule per emotion, and the "close" frame used for each blink are all
 * ported directly from that validated prototype.
 *
 * Wiring:
 *   SCK  -> D13    MOSI -> D11
 *   DC   -> D5     RST  -> D4   (shared)
 *   CS_L -> D9  (left display)
 *   CS_R -> D10 (right display)
 *   VCC  -> 3.3V   GND -> GND
 *
 * Flash budget: the seven bitmaps below total ~787 KB (7 x 112.5 KB) of
 * the STM32U585's 2 MB flash. Comfortable, but check the compiled
 * binary size after adding any further emotion art.
 * ---------------------------------------------------------------------
 */

#ifndef NOVA_EYES_H
#define NOVA_EYES_H

#include <Arduino.h>
#include <stdint.h>

// ── Eye states shared with the Python (MPU) side ────────────────────────
// Keep this list in sync with python/intelligence/intent.py EYE_* codes.
// Only states with real rendered art exist here -- there is intentionally
// no "surprised"/"thinking"/"sleepy" state until dedicated art is made.
enum NovaEyeState : int {
  EYE_NEUTRAL_CENTRE     = 0,  // normal_open_centre.h
  EYE_NEUTRAL_LOOK_LEFT  = 1,  // normal_open_left_looking.h
  EYE_NEUTRAL_LOOK_RIGHT = 2,  // normal_open_right_looking.h
  EYE_HAPPY              = 3,  // happy_open_left.h / happy_close_left.h
  EYE_ANGRY              = 4,  // angry_open_left.h
  // Placeholder: no dedicated "sad" art exists yet, so this reuses the
  // angry-open image mirrored on the opposite eye, matching the TODO in
  // the team's original ESP32 sketch. Replace once a real sad_*.h pair
  // is rendered.
  EYE_SAD                = 5
};

class NovaEyes {
public:
  NovaEyes(uint8_t pinRst, uint8_t pinDc, uint8_t pinCsLeft, uint8_t pinCsRight);

  // Initializes SPI + both GC9A01 panels, then displays EYE_NEUTRAL_CENTRE.
  void begin();

  // Displays the "open" image pair for the given state, applying the
  // correct per-state mirror rule (see NovaEyes.cpp's EYE_TABLE).
  void setState(int eyeState, bool force = false);

  // Plays a brief close -> open blink using the current state's own
  // "close" image and mirror rule (~100 ms closed, matching the
  // reference prototype's timing).
  void blink();

  // Call every loop() so idle behavior (automatic blink every few
  // seconds) runs without the Python side having to micromanage it.
  void update();

private:
  uint8_t _rst, _dc, _csL, _csR;
  int _currentState = -1;
  unsigned long _nextIdleBlinkAt = 0;

  enum MirrorMode : uint8_t { MIRROR_NONE, MIRROR_RIGHT, MIRROR_LEFT };

  struct EyeImageSet {
    const uint16_t *openImage;
    const uint16_t *closeImage;
    MirrorMode mirror;
  };

  EyeImageSet imagesForState(int eyeState) const;
  void showImages(const uint16_t *img, MirrorMode mirror);

  // Blits a full 240x240 PROGMEM RGB565 image to one panel, optionally
  // flipped horizontally (used for the "mirrored" eye of a pair).
  void pushImage(uint8_t cs, const uint16_t *img);
  void pushImageMirrored(uint8_t cs, const uint16_t *img);

  // Low-level GC9A01 register access (unchanged from the direct-SPI
  // approach validated in the team's original single-file prototype).
  void csSelect(uint8_t cs);
  void csDeselect(uint8_t cs);
  void dcCmd();
  void dcData();
  void writeCmd(uint8_t cs, uint8_t cmd);
  void writeCmdData(uint8_t cs, uint8_t cmd, const uint8_t *data, size_t len);
  void gc9a01Init(uint8_t cs);
  void setWindow(uint8_t cs, uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);
};

#endif // NOVA_EYES_H
