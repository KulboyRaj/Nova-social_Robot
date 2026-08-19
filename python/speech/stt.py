"""
speech/stt.py
---------------------------------------------------------------------
Speech-to-text. Per the report: "Uses Faster-Whisper + CTranslate2 to
process 16 kHz mono audio efficiently on the CPU", model "Whisper
base.en".

Provides:
  - record_audio(seconds) -> numpy float32 array          (mic capture)
  - transcribe(audio_array) -> str                         (STT)
  - listen_for_wake_word(wake_word) -> bool                (short-clip loop)
  - listen_for_command(max_seconds) -> str                 (full utterance)

Falls back from faster-whisper -> openai-whisper -> a clear error
message if neither package is installed, so the rest of the app can
still start up and log a useful message instead of crashing on import.
---------------------------------------------------------------------
"""

import logging
import time

import numpy as np
import sounddevice as sd

import config

logger = logging.getLogger("nova.stt")

_model = None
_backend = None  # "faster_whisper" or "openai_whisper"


def _load_model():
    global _model, _backend
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel
        _model = WhisperModel(
            config.WHISPER_MODEL_SIZE, device=config.WHISPER_DEVICE, compute_type="int8"
        )
        _backend = "faster_whisper"
        logger.info("Loaded faster-whisper model '%s' (CTranslate2, %s)",
                    config.WHISPER_MODEL_SIZE, config.WHISPER_DEVICE)
        return _model
    except ImportError:
        logger.warning("faster-whisper not installed, trying openai-whisper instead.")

    try:
        import whisper
        _model = whisper.load_model(config.WHISPER_MODEL_SIZE.replace(".en", ""))
        _backend = "openai_whisper"
        logger.info("Loaded openai-whisper model '%s'", config.WHISPER_MODEL_SIZE)
        return _model
    except ImportError as exc:
        raise RuntimeError(
            "Neither 'faster-whisper' nor 'openai-whisper' is installed. "
            "Run: pip install faster-whisper"
        ) from exc


def record_audio(seconds: float, sample_rate: int = None) -> np.ndarray:
    sample_rate = sample_rate or config.AUDIO_SAMPLE_RATE
    frames = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=config.MIC_DEVICE_INDEX,
    )
    sd.wait()
    return frames.flatten()


def transcribe(audio: np.ndarray) -> str:
    model = _load_model()
    if _backend == "faster_whisper":
        segments, _info = model.transcribe(audio, language="en", beam_size=1)
        return " ".join(seg.text.strip() for seg in segments).strip()
    else:  # openai_whisper expects float32 in [-1, 1] at 16kHz, same as ours
        result = model.transcribe(audio, language="en", fp16=False)
        return result.get("text", "").strip()


def listen_for_wake_word(wake_word: str = None, clip_seconds: float = 2.0) -> bool:
    """Records a short clip and checks whether it contains the wake phrase.

    This is a simple, always-on polling approach (not a dedicated
    low-power keyword spotter) -- adequate for a demo, but consider a
    lightweight wake-word engine (e.g. openWakeWord/Porcupine) for a
    production version so the full Whisper model isn't invoked in a
    tight loop.
    """
    wake_word = (wake_word or config.WAKE_WORD).lower().strip()
    audio = record_audio(clip_seconds)
    text = transcribe(audio).lower()
    if text:
        logger.debug("Wake-word listen heard: %r", text)
    return wake_word in text


def listen_for_command(max_seconds: float = 6.0) -> str:
    """Records a longer clip for the actual user command/question and
    returns the transcribed text."""
    logger.info("Listening for command (%.1fs)...", max_seconds)
    audio = record_audio(max_seconds)
    text = transcribe(audio)
    logger.info("Heard: %r", text)
    return text
