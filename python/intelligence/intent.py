"""
intelligence/intent.py
---------------------------------------------------------------------
Two jobs:

1. Map a detected facial emotion label (from perception/emotion.py,
   FER2013 label set) to the integer eye-state code the MCU sketch
   understands (must stay in sync with sketch/NovaEyes.h's
   NovaEyeState enum). Eye states are limited to the team's actual
   rendered art -- neutral (centre/look-left/look-right), happy, and
   angry, plus a sad placeholder that reuses the angry art until a
   dedicated sad image exists (see sketch/NovaEyes.h).

2. Very lightweight keyword-based intent parsing over the user's
   transcribed speech / the LLM's reply, to decide whether an action
   (light control, music, SOS, reminder) should also run alongside the
   spoken reply.

NOTE: This is intentionally simple substring/keyword matching, not a
proper NLU/slot-filling system. It's enough to demo "turn on the
light" / "play some music" / "call for help" / "remind me to..." but
will misfire on more creative phrasing. A good next step (mentioned in
the report's "What's Next") would be to have the LLM itself return a
small JSON action block instead of parsing raw text.
---------------------------------------------------------------------
"""

import re

# Keep this in sync with sketch/NovaEyes.h -> enum NovaEyeState.
# Only states with real rendered art exist here.
EYE_NEUTRAL_CENTRE = 0
EYE_NEUTRAL_LOOK_LEFT = 1
EYE_NEUTRAL_LOOK_RIGHT = 2
EYE_HAPPY = 3
EYE_ANGRY = 4
EYE_SAD = 5  # placeholder art (reuses angry image) -- see sketch/NovaEyes.h

# FER2013 label (from perception/emotion.py) -> eye state code. FER has
# classes with no rendered art yet (Surprise, Disgust); those map to the
# closest available expression rather than being invented.
FER_LABEL_TO_EYE_CODE = {
    "Angry": EYE_ANGRY,
    "Disgust": EYE_ANGRY,
    "Fear": EYE_SAD,
    "Happy": EYE_HAPPY,
    "Sad": EYE_SAD,
    "Surprise": EYE_NEUTRAL_CENTRE,  # no dedicated "surprised" art yet
    "Neutral": EYE_NEUTRAL_CENTRE,
}


def eye_code_for_mood(fer_label: str) -> int:
    return FER_LABEL_TO_EYE_CODE.get(fer_label, EYE_NEUTRAL_CENTRE)


def eye_code_for_gaze(x_offset: float, deadzone: float = 0.25) -> int:
    """Neutral-only gaze cue: when the tracked face is off to one side,
    look that direction using the team's normal_open_left/right_looking
    art instead of just the centre image. Only meaningful for neutral
    mood -- happy/angry/sad don't have left/right-looking variants.
    """
    if x_offset > deadzone:
        return EYE_NEUTRAL_LOOK_RIGHT
    if x_offset < -deadzone:
        return EYE_NEUTRAL_LOOK_LEFT
    return EYE_NEUTRAL_CENTRE


class ParsedIntent:
    def __init__(self, action="chat", params=None):
        self.action = action  # "chat" | "light_on" | "light_off" | "play_music" | "sos" | "reminder"
        self.params = params or {}

    def __repr__(self):
        return f"ParsedIntent(action={self.action!r}, params={self.params!r})"


_SOS_PATTERNS = ("sos", "emergency", "call for help", "i need help now", "help me now")
_LIGHT_ON_PATTERNS = ("turn on the light", "lights on", "switch on the light", "turn the light on")
_LIGHT_OFF_PATTERNS = ("turn off the light", "lights off", "switch off the light", "turn the light off")
_PLAY_PREFIX_PATTERN = re.compile(r"^.*?\bplay\b\s*(?:the|some|a)?\s*", re.IGNORECASE)
_TRAILING_MUSIC_WORDS_PATTERN = re.compile(r"\s*\b(?:song|music|track)\b\s*$", re.IGNORECASE)
_REMINDER_PATTERN = re.compile(r"\bremind me to\b\s*(?P<what>.+)", re.IGNORECASE)


def _extract_song_query(lowered_text: str) -> str:
    """'play some music' -> '' ; 'play the imperial march song' -> 'imperial march'."""
    after_play = _PLAY_PREFIX_PATTERN.sub("", lowered_text, count=1)
    return _TRAILING_MUSIC_WORDS_PATTERN.sub("", after_play).strip()


def parse_command(text: str) -> ParsedIntent:
    if not text:
        return ParsedIntent("chat")

    lowered = text.lower().strip()

    if any(p in lowered for p in _SOS_PATTERNS):
        return ParsedIntent("sos", {"raw_text": text})

    if any(p in lowered for p in _LIGHT_ON_PATTERNS) or ("light" in lowered and " on" in lowered):
        return ParsedIntent("light_on")

    if any(p in lowered for p in _LIGHT_OFF_PATTERNS) or ("light" in lowered and " off" in lowered):
        return ParsedIntent("light_off")

    reminder_match = _REMINDER_PATTERN.search(lowered)
    if reminder_match:
        return ParsedIntent("reminder", {"what": reminder_match.group("what").strip()})

    if lowered.startswith("play") or " play " in lowered:
        return ParsedIntent("play_music", {"query": _extract_song_query(lowered)})

    return ParsedIntent("chat", {"raw_text": text})
