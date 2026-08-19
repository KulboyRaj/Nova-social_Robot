"""
actions/reminders.py
---------------------------------------------------------------------
Very small reminders system: "remind me to <do something>" creates a
reminder that fires (spoken by Nova) a fixed delay later. Persisted to
a JSON file so reminders survive an app restart.

This is intentionally simple (no natural-language date/time parsing --
that's a good "What's Next" improvement). Every reminder created here
fires NOVA_REMINDER_DEFAULT_DELAY_MINUTES after it's created, unless
you extend `add_reminder` to parse a real time out of the request.
---------------------------------------------------------------------
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

import config

logger = logging.getLogger("nova.reminders")

DEFAULT_DELAY_MINUTES = int(os.getenv("NOVA_REMINDER_DEFAULT_DELAY_MINUTES", "15"))

_lock = threading.Lock()


def _load():
    if not os.path.isfile(config.REMINDERS_FILE):
        return []
    try:
        with open(config.REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Could not read reminders file (%s), starting empty.", exc)
        return []


def _save(reminders):
    with open(config.REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)


def add_reminder(what: str, delay_minutes: int = None) -> dict:
    delay_minutes = delay_minutes if delay_minutes is not None else DEFAULT_DELAY_MINUTES
    fire_at = (datetime.now() + timedelta(minutes=delay_minutes)).isoformat()
    reminder = {"what": what, "fire_at": fire_at, "fired": False}

    with _lock:
        reminders = _load()
        reminders.append(reminder)
        _save(reminders)

    logger.info("Reminder set: %r at %s", what, fire_at)
    return reminder


def pop_due_reminders() -> list:
    """Returns and marks-as-fired any reminders whose time has come.
    Call this periodically (e.g. once every loop iteration in main.py).
    """
    now = datetime.now()
    due = []

    with _lock:
        reminders = _load()
        changed = False
        for r in reminders:
            if not r["fired"] and datetime.fromisoformat(r["fire_at"]) <= now:
                r["fired"] = True
                due.append(r)
                changed = True
        if changed:
            _save(reminders)

    return due
