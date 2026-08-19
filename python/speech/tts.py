"""
speech/tts.py
---------------------------------------------------------------------
Text-to-speech. Defaults to pyttsx3 (fully offline, no API key/account
needed -- good for a demo and for keeping this repo free of any
required paid credentials). If you'd rather match a different TTS
engine mentioned in the report/pipeline (e.g. a cloud TTS), swap the
implementation of `speak()` below; everything else in the app just
calls `tts.speak(text)` and doesn't care how it's produced.
---------------------------------------------------------------------
"""

import logging
import threading

import config

logger = logging.getLogger("nova.tts")

_engine = None
_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        import pyttsx3
        _engine = pyttsx3.init()
        _engine.setProperty("rate", config.TTS_VOICE_RATE)
    return _engine


def speak(text: str):
    """Blocking call: speaks `text` out loud through the Bluetooth
    speaker (or whatever the default audio output is on the UNO Q).
    Called from main.py right after set_eye_state(...) so NOVA's face
    and voice change together.
    """
    if not text:
        return
    logger.info("Speaking: %r", text)
    with _lock:  # pyttsx3's engine is not safely re-entrant across threads
        try:
            engine = _get_engine()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:  # noqa: BLE001
            logger.error("TTS failed (%s). Falling back to text-only output.", exc)
            print(f"[NOVA would say]: {text}")
