"""
config.py
---------------------------------------------------------------------
Central place for every tunable/credential NOVA's Python side needs.
Everything is read from environment variables (loaded from a .env file
next to this app via python-dotenv), so nothing sensitive is hard-coded
in source that ends up on GitHub.

Copy .env.example (at the repo root) to .env and fill in real values.
Anything left blank falls back to a safe "disabled/simulated" mode --
see each actions/* module for exactly what happens when a credential
is missing.
---------------------------------------------------------------------
"""

import os
from dotenv import load_dotenv

# Loads a .env file if present. On the actual UNO Q / App Lab runtime,
# place your .env next to main.py (i.e. python/.env) or export the
# same variables in the app's environment.
load_dotenv()


def _bool(env_val, default=False):
    if env_val is None:
        return default
    return str(env_val).strip().lower() in ("1", "true", "yes", "on")


# ── General ──────────────────────────────────────────────────────────
WAKE_WORD = os.getenv("NOVA_WAKE_WORD", "hi nova")
ROBOT_NAME = os.getenv("NOVA_ROBOT_NAME", "Nova")
LOG_LEVEL = os.getenv("NOVA_LOG_LEVEL", "INFO")

# ── Camera / vision ──────────────────────────────────────────────────
CAMERA_INDEX = int(os.getenv("NOVA_CAMERA_INDEX", "0"))
CAMERA_WIDTH = int(os.getenv("NOVA_CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("NOVA_CAMERA_HEIGHT", "480"))
EMOTION_MODEL_PATH = os.getenv(
    "NOVA_EMOTION_MODEL_PATH", os.path.join(os.path.dirname(__file__), "models", "emotion_model.h5")
)

# ── Speech-to-text (Whisper / faster-whisper) ────────────────────────
WHISPER_MODEL_SIZE = os.getenv("NOVA_WHISPER_MODEL", "base.en")
WHISPER_DEVICE = os.getenv("NOVA_WHISPER_DEVICE", "cpu")
AUDIO_SAMPLE_RATE = int(os.getenv("NOVA_AUDIO_SAMPLE_RATE", "16000"))
MIC_DEVICE_INDEX = os.getenv("NOVA_MIC_DEVICE_INDEX")  # None = default mic
MIC_DEVICE_INDEX = int(MIC_DEVICE_INDEX) if MIC_DEVICE_INDEX not in (None, "") else None

# ── Text-to-speech ───────────────────────────────────────────────────
TTS_ENGINE = os.getenv("NOVA_TTS_ENGINE", "pyttsx3")  # "pyttsx3" is fully offline/free
TTS_VOICE_RATE = int(os.getenv("NOVA_TTS_RATE", "175"))

# ── LLM (Ollama, matching the report's Qwen2.5-1.5B-Instruct) ────────
OLLAMA_HOST = os.getenv("NOVA_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("NOVA_OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
LLM_TIMEOUT_SECONDS = int(os.getenv("NOVA_LLM_TIMEOUT", "20"))

# ── Bridge (Python <-> MCU sketch) ───────────────────────────────────
# When True and the arduino.app_utils Bridge module can't be imported
# (e.g. you're running main.py on a laptop for a quick logic test
# instead of on the actual UNO Q inside App Lab), bridge_client.py
# falls back to a "dummy" bridge that just logs what it would have
# sent, so the rest of the app still runs for a demo/dry-run.
ALLOW_DUMMY_BRIDGE = _bool(os.getenv("NOVA_ALLOW_DUMMY_BRIDGE"), default=True)

# ── IoT / smart light control ────────────────────────────────────────
IOT_METHOD = os.getenv("NOVA_IOT_METHOD", "mqtt")  # "mqtt" or "home_assistant"

MQTT_BROKER_HOST = os.getenv("NOVA_MQTT_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("NOVA_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("NOVA_MQTT_USER", "")            # placeholder - fill in your broker's user
MQTT_PASSWORD = os.getenv("NOVA_MQTT_PASS", "")            # placeholder - fill in your broker's pass
MQTT_LIGHT_TOPIC = os.getenv("NOVA_MQTT_LIGHT_TOPIC", "nova/home/light")

HOME_ASSISTANT_URL = os.getenv("NOVA_HA_URL", "http://homeassistant.local:8123")
HOME_ASSISTANT_TOKEN = os.getenv("NOVA_HA_TOKEN", "")       # placeholder - long-lived HA access token
HOME_ASSISTANT_LIGHT_ENTITY = os.getenv("NOVA_HA_LIGHT_ENTITY", "light.living_room")

# ── Music playback ───────────────────────────────────────────────────
MUSIC_METHOD = os.getenv("NOVA_MUSIC_METHOD", "local")  # "spotify" or "local"
SPOTIFY_CLIENT_ID = os.getenv("NOVA_SPOTIFY_CLIENT_ID", "")        # placeholder
SPOTIFY_CLIENT_SECRET = os.getenv("NOVA_SPOTIFY_CLIENT_SECRET", "")  # placeholder
SPOTIFY_REDIRECT_URI = os.getenv("NOVA_SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
LOCAL_MUSIC_DIR = os.getenv(
    "NOVA_LOCAL_MUSIC_DIR", os.path.join(os.path.dirname(__file__), "music")
)

# ── SOS / emergency calling (Twilio) ──────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("NOVA_TWILIO_SID", "")        # placeholder
TWILIO_AUTH_TOKEN = os.getenv("NOVA_TWILIO_TOKEN", "")       # placeholder
TWILIO_FROM_NUMBER = os.getenv("NOVA_TWILIO_FROM", "")       # placeholder, e.g. "+15551234567"
SOS_CONTACT_NUMBER = os.getenv("NOVA_SOS_TO", "")            # placeholder, e.g. "+15557654321"
SOS_MESSAGE = os.getenv(
    "NOVA_SOS_MESSAGE",
    "This is an automated emergency alert from Nova. The person you are "
    "monitoring may need immediate assistance. Please check on them now."
)

# ── Reminders ─────────────────────────────────────────────────────────
REMINDERS_FILE = os.getenv(
    "NOVA_REMINDERS_FILE", os.path.join(os.path.dirname(__file__), "reminders.json")
)
