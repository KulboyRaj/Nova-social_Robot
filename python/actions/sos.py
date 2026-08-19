"""
actions/sos.py
---------------------------------------------------------------------
Places an emergency phone call using Twilio's Programmable Voice API
when the user says something matching the SOS intent (see
intelligence/intent.py's _SOS_PATTERNS).

Twilio is used because it's the standard, well-documented way to place
an outbound PSTN call from an application without building your own
telephony stack. Requires a Twilio account (a free trial account can
place real calls to verified numbers, which is enough for a demo).

Credentials (all placeholders in .env.example -- fill in your own):
  NOVA_TWILIO_SID    - Twilio Account SID
  NOVA_TWILIO_TOKEN  - Twilio Auth Token
  NOVA_TWILIO_FROM   - Twilio phone number you own, E.164 format
  NOVA_SOS_TO        - the emergency contact's number, E.164 format

If any of these are blank, `trigger_sos()` logs what it *would* have
done instead of calling the Twilio API, so the rest of the demo still
runs without a Twilio account set up.
---------------------------------------------------------------------
"""

import logging

import config

logger = logging.getLogger("nova.sos")


def trigger_sos(reason: str = "") -> bool:
    if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN
            and config.TWILIO_FROM_NUMBER and config.SOS_CONTACT_NUMBER):
        logger.warning(
            "[SIMULATED SOS] Twilio credentials not fully configured -- "
            "would have called %s and said: %r. Fill in NOVA_TWILIO_* and "
            "NOVA_SOS_TO in .env to actually place the call. (reason=%r)",
            config.SOS_CONTACT_NUMBER or "<no number set>", config.SOS_MESSAGE, reason,
        )
        return False

    try:
        from twilio.rest import Client

        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        twiml = f"<Response><Say>{config.SOS_MESSAGE}</Say></Response>"

        call = client.calls.create(
            to=config.SOS_CONTACT_NUMBER,
            from_=config.TWILIO_FROM_NUMBER,
            twiml=twiml,
        )
        logger.critical("SOS call placed to %s (Twilio call sid=%s). reason=%r",
                         config.SOS_CONTACT_NUMBER, call.sid, reason)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to place SOS call via Twilio: %s", exc)
        return False
