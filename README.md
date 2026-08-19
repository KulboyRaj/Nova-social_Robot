# NOVA — The Next Generation Human-Centric Social Robot

**Arduino Physical AI Challenge India 2026** · Team NOVA · Robu.in × Arduino
Team ID: APC-2026-GJ-76197 · LDCE, Ahmedabad

NOVA is a human-centric social robot built on the **Arduino UNO Q**. It sees
the person in front of it (face and emotion detection via a USB webcam),
listens and responds in natural conversation (wake-word activation →
speech-to-text → a locally-running LLM → text-to-speech), expresses itself
through two animated round-display eyes, physically turns its head to
follow the person, and can control smart lights, play music, set
reminders, and place an emergency call — all from a single board.

---

## Features

- **Perception** — real-time face detection and facial emotion
  recognition from a USB webcam.
- **Conversation** — wake-word activation ("Hi Nova"), speech-to-text via
  Whisper, natural-language responses from a locally hosted
  Qwen2.5-1.5B-Instruct model (Ollama), and offline text-to-speech.
- **Expressive eyes** — two round GC9A01 displays render Nova's mood
  (happy, sad, surprised, thinking, angry, sleepy, listening, neutral) and
  blink automatically between interactions.
- **Human-following head** — a servo motor rotates Nova's head to keep the
  detected face centered.
- **Smart home control** — voice-triggered light on/off via MQTT or Home
  Assistant.
- **Music playback** — voice-triggered playback via Spotify or a local
  music library.
- **Reminders** — simple voice-set reminders that Nova announces later.
- **SOS / emergency calling** — a spoken distress phrase places an
  automated phone call to a configured emergency contact via Twilio.

## How it works

```
USB Webcam ──▶ face + emotion detection ──▶ head-tracking servo angle
                                        └──▶ idle mood reflected in the eyes

Microphone ──▶ wake word ("Hi Nova") ──▶ speech-to-text ──▶ intent routing
                                                                │
                                        ┌───────────────────────┼──────────────────────┐
                                        ▼                       ▼                      ▼
                               conversational reply      smart light / music     reminder / SOS
                              (local LLM + eyes + TTS)     (MQTT or API call)     (scheduled / call)
```

## Hardware (Bill of Materials)

| Component | Qty |
|---|---|
| Arduino UNO Q (ABX00087) | 1 |
| Logitech USB Webcam | 1 |
| 1.28" round GC9A01 display | 2 |
| MG996R Servo Motor | 1 |
| Bluetooth Speaker | 1 |
| Power Adapter | 1 |
| USB Hub | 1 |

## Architecture

The Arduino UNO Q combines two processors on one board, and this project
splits responsibilities accordingly:

| Side | Chip | OS / Core | Responsibility |
|---|---|---|---|
| MPU (Linux) | Qualcomm® Dragonwing™ QRB2210 | Debian Linux | Camera, emotion CNN, speech recognition, the LLM, text-to-speech, IoT/music/SOS integrations |
| MCU (sketch) | STMicroelectronics STM32U585 | Arduino Core for Zephyr | Eye displays, head servo, real-time hardware timing |

The two sides communicate over Arduino's Bridge (RPC) library, exposed to
Python as `arduino.app_utils.Bridge` and to the sketch as
`Arduino_RouterBridge.h`.

**Display driver:** the two GC9A01 "eye" displays are driven by a
self-contained direct-SPI driver (`sketch/NovaEyes.h` / `.cpp`) rather than
LovyanGFX. UNO Q's microcontroller runs Arduino Core for Zephyr on an
STM32U585 — a different architecture from ESP32/RP2040, which is what
LovyanGFX targets. Its SPI/DMA fast paths call ESP-IDF-specific APIs that
don't exist under Zephyr, so the library isn't available for this board
regardless of installation method. `NovaEyes` instead talks to the GC9A01
controller directly over the standard `SPI.h` API and blits the team's
own pre-rendered 240×240 RGB565 emotion bitmaps (~112.5 KB each, ~787 KB
total for all seven — comfortably inside the STM32U585's 2 MB flash),
reproducing the exact per-emotion mirror rule (which eye gets flipped
horizontally, and which "closed" frame each blink uses) validated in the
team's original ESP32/LovyanGFX prototype.

Eye states currently have real rendered art for: neutral (centre,
look-left, look-right), happy, and angry. "Sad" is wired up as a
placeholder that reuses the angry artwork (mirrored on the other eye)
until a dedicated sad image is rendered — see `sketch/NovaEyes.h`.

## Repository layout

This follows the standard Arduino UNO Q application layout (a Python
folder for the Linux/MPU side, a sketch folder for the microcontroller
side, and a top-level manifest), so it can be deployed directly through
Arduino App Lab or `arduino-app-cli`:

```
nova-robot/
├── README.md
├── app.yaml                    Arduino App Lab manifest
├── .env.example                 Configuration template
├── python/                      Runs on the Linux (MPU) side
│   ├── main.py                   Orchestrator
│   ├── config.py                  Settings, loaded from .env
│   ├── bridge_client.py            Python <-> MCU Bridge wrapper
│   ├── requirements.txt
│   ├── perception/
│   │   ├── camera.py                Face detection + head-tracking offset
│   │   └── emotion.py               Facial emotion recognition
│   ├── speech/
│   │   ├── stt.py                    Wake word + speech-to-text
│   │   └── tts.py                    Text-to-speech
│   ├── intelligence/
│   │   ├── llm.py                     Conversational LLM (Ollama)
│   │   └── intent.py                  Intent parsing + mood-to-expression mapping
│   ├── actions/
│   │   ├── iot_control.py             Smart light control (MQTT / Home Assistant)
│   │   ├── music.py                   Music playback (Spotify / local library)
│   │   ├── sos.py                      Emergency calling (Twilio)
│   │   └── reminders.py                Reminders
│   ├── models/                        Trained model weights (see models/README.md)
│   └── music/                         Local music library for playback fallback
└── sketch/                       Runs on the microcontroller (MCU) side
    ├── sketch.ino                     Bridge-exposed functions, servo + eye control
    ├── sketch.yaml                     Board/library configuration
    ├── NovaEyes.h                      Dual GC9A01 eye display driver
    ├── NovaEyes.cpp
    ├── normal_open_centre.h            Eye artwork: neutral, centre, open
    ├── normal_close_centre.h           Eye artwork: neutral, centre, closed (blink)
    ├── normal_open_left_looking.h      Eye artwork: neutral, looking left
    ├── normal_open_right_looking.h     Eye artwork: neutral, looking right
    ├── happy_open_left.h               Eye artwork: happy, open
    ├── happy_close_left.h              Eye artwork: happy, closed (blink)
    └── angry_open_left.h               Eye artwork: angry, open (also used as the sad placeholder)
```


## Local model weights (not stored in this repo)

Two model files this app can use are intentionally **not** committed to
git — they're large binaries and Nova falls back to simpler behavior if
they're missing, so they're kept out of the repo history. Instead of
downloading them by hand, just run:

```bash
bash scripts/download_models.sh
```

This fetches:
- `python/models/emotion_model.h5` — a FER2013 7-emotion CNN (MIT-licensed public checkpoint). Without it, emotion detection falls back to a simple smile/neutral heuristic.
- `qwen2.5-1.5b-instruct-q4_k_m.gguf` — the LLM weights for the local Ollama model `qwen2.5:1.5b-instruct`, from this repo's [`llm-weights-v1` release](https://github.com/KulboyRaj/Nova-social_Robot/releases/tag/llm-weights-v1), checksum-verified on download.

The LLM file is raw model weights, not something Ollama can load directly
from a path — it needs to be imported into Ollama under the exact model
name `config.py` expects:

```bash
ollama create qwen2.5:1.5b-instruct -f Modelfile
curl http://localhost:11434/api/chat -d '{"model":"qwen2.5:1.5b-instruct","messages":[{"role":"user","content":"hi"}],"stream":false}'
```

## Getting started

1. **Deploy to the board.** Push this project to the UNO Q using Arduino
   App Lab, or via SSH/SCP and the Arduino CLI:
   ```bash
   scp -r * arduino@<UNO_Q_IP_ADDRESS>:~/ArduinoApps/nova-robot/
   ssh arduino@<UNO_Q_IP_ADDRESS>
   arduino-app-cli app start ~/ArduinoApps/nova-robot
   ```
2. **Install Python dependencies** on the board:
   ```bash
   cd ~/ArduinoApps/nova-robot/python
   pip install -r requirements.txt --break-system-packages
   ```
3. **Add the MCU library.** In App Lab's sketch editor (or via
   `sketch.yaml`), add the **Servo** library — the only external
   dependency the sketch needs.
4. **Configure integrations (optional).** Copy `.env.example` to
   `python/.env` and fill in credentials for any of the smart light,
   music, or SOS integrations you want active. Any left blank run in a
   logged, no-op mode so the rest of the app is unaffected.
5. **Run the app** from App Lab, or:
   ```bash
   arduino-app-cli app logs ~/ArduinoApps/nova-robot
   ```
6. Say **"Hi Nova"**, wait for the eyes to switch to the listening
   expression, then speak a question or command (e.g. "turn on the
   light", "play some music", "remind me to take my medicine").

## Roadmap

- Replace keyword-based intent parsing (`intelligence/intent.py`) with
  structured intent output from the LLM itself.
- Replace the polling-based wake-word check with a dedicated low-power
  wake-word engine.
- Render dedicated "sad" and "surprised" eye artwork to replace the
  current placeholders (sad currently reuses the angry image; surprised
  falls back to neutral).
- Expand the eye-expression library with additional transitional
  animations (subtle eye movement, gradual mood shifts).
- Combine facial emotion, voice tone, and conversation history for more
  context-aware responses.
- Add personalized voice generation, learned from a short user voice
  sample.

## Team

Yashvi Shah (Team Lead) · Tanishq Agrawal · Pruthviraj Banne · Raj Teli
