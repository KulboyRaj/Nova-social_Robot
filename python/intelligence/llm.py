"""
intelligence/llm.py
---------------------------------------------------------------------
Conversational intelligence via a locally-running Ollama server, model
"qwen2.5:1.5b-instruct" (matches the report's "Qwen2.5-1.5B-Instruct").
No API key needed -- Ollama runs entirely on-device.

Requires Ollama to be installed and running, with the model pulled:
`ollama pull qwen2.5:1.5b-instruct`.
---------------------------------------------------------------------
"""

import logging

import requests

import config

logger = logging.getLogger("nova.llm")

SYSTEM_PROMPT = """You are Nova, a warm, friendly social companion robot.
You can see the person's face and have a rough read on their mood, hear
what they say, and respond with both speech and a facial expression.
Keep replies short (1-3 sentences) and conversational, suitable for being
spoken out loud. If the user asks you to control a light, play music, or
raise an emergency/SOS alert, acknowledge it naturally in your reply --
a separate system will handle actually carrying out the action.
"""


def _build_prompt(user_text: str, detected_mood: str = None, conversation_history=None) -> list:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history[-6:])  # keep prompt small/fast
    context = user_text
    if detected_mood:
        context = f"[The person appears to look {detected_mood.lower()} right now.] {user_text}"
    messages.append({"role": "user", "content": context})
    return messages


def generate_reply(user_text: str, detected_mood: str = None, conversation_history=None) -> str:
    """Sends the conversation to the local Ollama model and returns
    Nova's reply text. Falls back to a canned response if Ollama isn't
    reachable, so a demo doesn't hard-crash if the server isn't running.
    """
    messages = _build_prompt(user_text, detected_mood, conversation_history)

    try:
        response = requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={"model": config.OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("message", {}).get("content", "").strip()
        if reply:
            return reply
        logger.warning("Ollama returned an empty reply.")
    except requests.exceptions.RequestException as exc:
        logger.error(
            "Could not reach Ollama at %s (%s). Is `ollama serve` running and "
            "has `ollama pull %s` been run?",
            config.OLLAMA_HOST, exc, config.OLLAMA_MODEL,
        )

    return "I'm having trouble thinking right now, but I'm still here with you."


def generate_proactive_checkin(detected_mood: str) -> str:
    """Used when no conversation is happening: asks a short question or
    makes a comment appropriate to the detected mood, so Nova doesn't
    just sit there silently (per the report's idle interaction loop).
    """
    prompt = (
        f"The person you're watching looks {detected_mood.lower()}. Say one short, "
        f"caring sentence to them that fits that mood -- either a gentle question "
        f"or a supportive comment. Do not mention that you're 'detecting' their "
        f"emotion; just speak naturally."
    )
    return generate_reply(prompt)
