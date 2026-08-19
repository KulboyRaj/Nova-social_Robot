r"""
main.py
---------------------------------------------------------------------
NOVA - Python (MPU/Linux) side entry point. Runs on the Qualcomm
QRB2210 side of the UNO Q, inside Arduino App Lab (or via
`arduino-app-cli app start`).

Overall flow (matches the project report's block diagram):

  Camera --> face + emotion detection --------\
                                                >--> eyes (via Bridge) / idle mood check-in speech
  Mic (wake word "hi nova") --> STT --> LLM --> intent parsing --> TTS
                                             \--> IoT light / music / SOS / reminders

Three background daemon threads plus the voice loop on the main thread:
  - vision_loop        : camera -> face/emotion -> head-tracking servo
                          angle + idle eye expression
  - idle_checkin_loop  : occasionally speaks a short mood-based comment
                          when nobody is actively talking to Nova
  - reminders_loop     : fires any due reminders
  - voice_loop (main)  : wake-word -> command -> LLM/intent -> action + TTS

See README.md for the full architecture write-up and setup instructions.
---------------------------------------------------------------------
"""

import logging
import random
import threading
import time

import config
import bridge_client
from perception.camera import CameraWorker
from perception.emotion import EmotionDetector
from speech import stt, tts
from intelligence import llm, intent
from actions import iot_control, music, sos, reminders

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("nova.main")


class SharedState:
    """Thread-safe blackboard between the vision, voice and idle threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self.mood = "Neutral"
        self.face_present = False
        self.x_offset = 0.0
        self.conversation_active = False

    def update_vision(self, mood, face_present, x_offset):
        with self._lock:
            self.mood = mood
            self.face_present = face_present
            self.x_offset = x_offset

    def snapshot(self):
        with self._lock:
            return self.mood, self.face_present, self.x_offset

    def set_conversation_active(self, active: bool):
        with self._lock:
            self.conversation_active = active

    def is_conversation_active(self) -> bool:
        with self._lock:
            return self.conversation_active


state = SharedState()
stop_event = threading.Event()


# ═══════════════════════════════════════════════════════════════════════
#  Background threads
# ═══════════════════════════════════════════════════════════════════════

def vision_loop():
    """Perception loop: face detection -> emotion -> head-tracking servo
    angle, and (when nobody is actively conversing) keeps NOVA's eyes
    reflecting the detected mood."""
    camera = CameraWorker()
    emotion_detector = EmotionDetector()

    try:
        camera.open()
    except RuntimeError as exc:
        logger.error("Camera unavailable (%s). Vision + head-tracking disabled; "
                     "voice features still work.", exc)
        return

    last_angle_sent = None
    try:
        while not stop_event.is_set():
            obs = camera.read()

            if obs.found:
                mood = emotion_detector.detect(obs.frame, obs.face_box)
                state.update_vision(mood, True, obs.x_offset)

                # Human-follower: turn head toward the tracked face.
                # x_offset is -1 (face at left edge) .. +1 (face at right
                # edge); map to a 20-160 degree servo sweep around center.
                angle = int(90 + obs.x_offset * 60)
                angle = max(20, min(160, angle))
                if angle != last_angle_sent:
                    bridge_client.set_head_angle(angle)
                    last_angle_sent = angle

                if not state.is_conversation_active():
                    if mood == "Neutral":
                        # Only the neutral expression has look-left/right
                        # art, so use it to add a gaze cue while tracking.
                        bridge_client.set_eye_state(intent.eye_code_for_gaze(obs.x_offset))
                    else:
                        bridge_client.set_eye_state(intent.eye_code_for_mood(mood))
            else:
                state.update_vision("Neutral", False, 0.0)
                # No dedicated "nobody's here" art exists -- leave the eyes
                # showing whatever they last displayed rather than forcing
                # a state that doesn't have real art behind it.

            time.sleep(0.15)
    finally:
        camera.close()


def idle_checkin_loop():
    """When a face has been present for a while with no conversation
    happening, occasionally have Nova speak a short mood-based line."""
    next_checkin_at = time.time() + 20
    while not stop_event.is_set():
        time.sleep(1)
        mood, face_present, _ = state.snapshot()

        if face_present and not state.is_conversation_active() and time.time() >= next_checkin_at:
            state.set_conversation_active(True)
            try:
                bridge_client.set_eye_state(intent.eye_code_for_mood(mood))
                text = llm.generate_proactive_checkin(mood)
                tts.speak(text)
            except Exception as exc:  # noqa: BLE001
                logger.error("Idle check-in failed: %s", exc)
            finally:
                state.set_conversation_active(False)
            next_checkin_at = time.time() + random.uniform(45, 90)


def reminders_loop():
    while not stop_event.is_set():
        try:
            for r in reminders.pop_due_reminders():
                state.set_conversation_active(True)
                try:
                    bridge_client.set_eye_state(intent.EYE_NEUTRAL_CENTRE)
                    tts.speak(f"Just a reminder: {r['what']}")
                finally:
                    state.set_conversation_active(False)
        except Exception as exc:  # noqa: BLE001
            logger.error("Reminder check failed: %s", exc)
        time.sleep(5)


# ═══════════════════════════════════════════════════════════════════════
#  Conversation handling
# ═══════════════════════════════════════════════════════════════════════

def handle_intent(parsed: intent.ParsedIntent, user_text: str, mood: str):
    if parsed.action == "sos":
        # No dedicated "alarmed" art exists; angry is the closest available
        # expression for signaling urgency.
        bridge_client.set_eye_state(intent.EYE_ANGRY)
        sos.trigger_sos(reason=user_text)
        tts.speak("I've alerted your emergency contact right away. Help is on the way.")

    elif parsed.action == "light_on":
        iot_control.turn_light_on()
        bridge_client.set_eye_state(intent.EYE_HAPPY)
        tts.speak("Sure, turning the light on for you.")

    elif parsed.action == "light_off":
        iot_control.turn_light_off()
        bridge_client.set_eye_state(intent.EYE_NEUTRAL_CENTRE)
        tts.speak("Okay, turning the light off.")

    elif parsed.action == "play_music":
        query = parsed.params.get("query") or "something you'll like"
        bridge_client.set_eye_state(intent.EYE_HAPPY)
        music.play(parsed.params.get("query", ""))
        tts.speak(f"Playing {query} for you now.")

    elif parsed.action == "reminder":
        what = parsed.params.get("what", "your reminder")
        reminders.add_reminder(what)
        bridge_client.set_eye_state(intent.EYE_NEUTRAL_CENTRE)
        tts.speak(f"Got it, I'll remind you to {what}.")

    else:  # plain conversation
        bridge_client.set_eye_state(intent.EYE_NEUTRAL_CENTRE)  # no dedicated "thinking" art yet
        reply = llm.generate_reply(user_text, detected_mood=mood)
        bridge_client.set_eye_state(intent.eye_code_for_mood(mood))
        tts.speak(reply)


def voice_loop():
    """Main thread: continuously listens for the wake word, then handles
    one full command each time it's heard."""
    logger.info("Voice loop started -- listening for wake word %r", config.WAKE_WORD)

    while not stop_event.is_set():
        try:
            heard_wake = stt.listen_for_wake_word()
        except Exception as exc:  # noqa: BLE001
            logger.error("Wake-word listening failed (%s); retrying shortly.", exc)
            time.sleep(2)
            continue

        if not heard_wake:
            continue

        state.set_conversation_active(True)
        try:
            bridge_client.trigger_blink()
            bridge_client.set_eye_state(intent.EYE_NEUTRAL_CENTRE)  # no dedicated "listening" art yet

            user_text = stt.listen_for_command()
            if not user_text:
                tts.speak("Sorry, I didn't catch that.")
                continue

            mood, _, _ = state.snapshot()
            parsed = intent.parse_command(user_text)
            logger.info("Parsed intent: %s", parsed)
            handle_intent(parsed, user_text, mood)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error handling voice command: %s", exc)
            tts.speak("Sorry, something went wrong on my end.")
        finally:
            state.set_conversation_active(False)


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════

def main():
    logger.info("NOVA starting up (robot name: %s)...", config.ROBOT_NAME)
    if bridge_client.is_dummy():
        logger.warning(
            "Running with a DummyBridge -- this means arduino.app_utils "
            "wasn't importable, so eye/servo calls will only be logged, "
            "not sent to real hardware. Run this inside App Lab on the "
            "actual UNO Q for the real thing."
        )

    threads = [
        threading.Thread(target=vision_loop, daemon=True, name="nova-vision"),
        threading.Thread(target=idle_checkin_loop, daemon=True, name="nova-idle-checkin"),
        threading.Thread(target=reminders_loop, daemon=True, name="nova-reminders"),
    ]
    for t in threads:
        t.start()

    try:
        voice_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down NOVA...")
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
