"""
bridge_client.py
---------------------------------------------------------------------
Thin wrapper around Arduino App Lab's Python-side Bridge, used to talk
to the functions exposed by sketch/sketch.ino (set_eye_state,
trigger_blink, set_head_angle, get_head_angle).

`from arduino.app_utils import Bridge` only exists inside the App Lab
Python runtime on the actual UNO Q. So that this repo can also be
sanity-checked (imports, logic, intent parsing, etc.) on a regular
laptop without a board attached, this module falls back to a
DummyBridge that just logs calls instead of crashing, when
config.ALLOW_DUMMY_BRIDGE is True (the default).

On the real board, running inside App Lab, the real Bridge is used
automatically -- no code changes needed.
---------------------------------------------------------------------
"""

import logging
import config

logger = logging.getLogger("nova.bridge")

_bridge = None
_using_dummy = False


class DummyBridge:
    """Stand-in for arduino.app_utils.Bridge when not running on the board."""

    def call(self, function_name, *args):
        logger.debug("[DummyBridge] would call %s%s", function_name, args)
        # Reasonable fake return values so callers don't crash on type().
        if function_name == "get_head_angle":
            return 90
        return None


def get_bridge():
    """Returns a ready-to-use Bridge object (real or dummy)."""
    global _bridge, _using_dummy
    if _bridge is not None:
        return _bridge

    try:
        from arduino.app_utils import Bridge  # real bridge, only on-device
        _bridge = Bridge
        _using_dummy = False
        logger.info("Connected to real Arduino Bridge (MCU sketch).")
    except ImportError:
        if not config.ALLOW_DUMMY_BRIDGE:
            raise
        _bridge = DummyBridge()
        _using_dummy = True
        logger.warning(
            "arduino.app_utils.Bridge not available (not running inside "
            "App Lab on the UNO Q) -- using DummyBridge. Eyes/servo calls "
            "will be logged, not actually sent. This is expected if you're "
            "just testing the Python logic on a laptop."
        )
    return _bridge


def is_dummy():
    get_bridge()
    return _using_dummy


# ── Convenience wrappers used by the rest of the app ─────────────────

def set_eye_state(eye_state: int):
    try:
        get_bridge().call("set_eye_state", int(eye_state))
    except Exception as exc:  # noqa: BLE001 - bridge calls should never crash the app
        logger.error("set_eye_state(%s) failed: %s", eye_state, exc)


def trigger_blink():
    try:
        get_bridge().call("trigger_blink")
    except Exception as exc:  # noqa: BLE001
        logger.error("trigger_blink() failed: %s", exc)


def set_head_angle(angle_deg: int):
    try:
        get_bridge().call("set_head_angle", int(angle_deg))
    except Exception as exc:  # noqa: BLE001
        logger.error("set_head_angle(%s) failed: %s", angle_deg, exc)


def get_head_angle() -> int:
    try:
        return int(get_bridge().call("get_head_angle"))
    except Exception as exc:  # noqa: BLE001
        logger.error("get_head_angle() failed: %s", exc)
        return 90
