"""
actions/iot_control.py
---------------------------------------------------------------------
Turns a smart light on/off. Two official/standard methods are wired
up; pick one with NOVA_IOT_METHOD in .env:

  - "mqtt"            : publishes ON/OFF to a topic on any MQTT broker
                        (Mosquitto, Home Assistant's built-in broker,
                        Tasmota/Zigbee2MQTT bridges, etc). This is the
                        most universally "official" way to control IoT
                        devices without tying to one vendor's cloud API.
  - "home_assistant"  : calls Home Assistant's REST API directly
                        (POST /api/services/light/turn_on|turn_off).

Both use placeholder credentials in .env.example -- fill in your own
broker/HA details, or leave them blank to run in a safe "simulated"
mode that just logs what it would have done (useful for a demo without
real hardware wired up).
---------------------------------------------------------------------
"""

import logging

import config

logger = logging.getLogger("nova.iot")


def _mqtt_publish(payload: str):
    if not config.MQTT_BROKER_HOST:
        logger.info("[SIMULATED MQTT] would publish %r to %r", payload, config.MQTT_LIGHT_TOPIC)
        return

    try:
        import paho.mqtt.publish as mqtt_publish
    except ImportError:
        logger.warning(
            "[SIMULATED MQTT] paho-mqtt is not installed (pip install paho-mqtt) "
            "-- would publish %r to %r", payload, config.MQTT_LIGHT_TOPIC,
        )
        return

    auth = None
    if config.MQTT_USERNAME:
        auth = {"username": config.MQTT_USERNAME, "password": config.MQTT_PASSWORD}

    try:
        mqtt_publish.single(
            config.MQTT_LIGHT_TOPIC,
            payload=payload,
            hostname=config.MQTT_BROKER_HOST,
            port=config.MQTT_BROKER_PORT,
            auth=auth,
        )
        logger.info("Published %r to MQTT topic %r", payload, config.MQTT_LIGHT_TOPIC)
    except Exception as exc:  # noqa: BLE001 - broker connection issues shouldn't crash the app
        logger.error("MQTT publish failed: %s", exc)


def _home_assistant_call(service: str):
    import requests  # local import keeps this optional dependency lazy

    if not config.HOME_ASSISTANT_TOKEN:
        logger.info(
            "[SIMULATED Home Assistant] would call light.%s on %r",
            service, config.HOME_ASSISTANT_LIGHT_ENTITY,
        )
        return

    url = f"{config.HOME_ASSISTANT_URL}/api/services/light/{service}"
    headers = {
        "Authorization": f"Bearer {config.HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {"entity_id": config.HOME_ASSISTANT_LIGHT_ENTITY}

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info("Home Assistant light.%s -> %s", service, resp.status_code)
    except requests.exceptions.RequestException as exc:
        logger.error("Home Assistant call failed: %s", exc)


def turn_light_on():
    if config.IOT_METHOD == "home_assistant":
        _home_assistant_call("turn_on")
    else:
        _mqtt_publish("ON")


def turn_light_off():
    if config.IOT_METHOD == "home_assistant":
        _home_assistant_call("turn_off")
    else:
        _mqtt_publish("OFF")
