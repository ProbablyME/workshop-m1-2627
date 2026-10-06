"""Pont MQTT ↔ base ↔ WebSocket.

Tourne dans le thread réseau de paho ; les écritures en base se font avec une
session dédiée et la diffusion WebSocket est renvoyée vers la boucle asyncio.
"""
import asyncio
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from . import schemas, services
from .config import settings
from .db import SessionLocal
from .ws import manager

log = logging.getLogger(__name__)


class MqttBridge:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            clean_session=True,
        )
        if settings.mqtt_user:
            self.client.username_pw_set(settings.mqtt_user, settings.mqtt_password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    # --- cycle de vie ---
    def start(self) -> None:
        log.info("MQTT → %s:%s (prefix %s)", settings.mqtt_host, settings.mqtt_port, settings.mqtt_topic_prefix)
        self.client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def publish(self, suffix: str, payload: dict[str, Any], qos: int = 1, retain: bool = False) -> bool:
        info = self.client.publish(settings.topic(suffix), json.dumps(payload), qos=qos, retain=retain)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    # --- callbacks paho (thread réseau) ---
    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:  # noqa: ANN001
        if reason_code != 0:
            log.error("MQTT connexion refusée : %s", reason_code)
            return
        self.connected = True
        for suffix in ("telemetry", "alerts", "status", "ai"):
            client.subscribe(settings.topic(suffix), qos=1)
        log.info("MQTT connecté, abonné à %s/#", settings.mqtt_topic_prefix)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:  # noqa: ANN001
        self.connected = False
        log.warning("MQTT déconnecté (%s), reconnexion automatique…", reason_code)

    def _on_message(self, client, userdata, msg) -> None:  # noqa: ANN001
        suffix = msg.topic.removeprefix(settings.mqtt_topic_prefix + "/")
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("MQTT payload illisible sur %s : %r", msg.topic, msg.payload[:80])
            return
        try:
            self._dispatch(suffix, payload)
        except ValidationError as exc:
            log.warning("MQTT payload invalide sur %s : %s", msg.topic, exc.errors()[:3])
        except Exception:  # noqa: BLE001
            log.exception("Erreur de traitement du message MQTT %s", msg.topic)

    def _dispatch(self, suffix: str, payload: dict[str, Any]) -> None:
        with SessionLocal() as db:
            if suffix == "telemetry":
                row = services.record_telemetry(db, schemas.TelemetryIn.model_validate(payload))
                self._broadcast("telemetry", schemas.TelemetryOut.model_validate(row))
            elif suffix == "alerts":
                row = services.record_alert(db, schemas.AlertIn.model_validate(payload), source="esp")
                self._broadcast("alert", schemas.AlertOut.model_validate(row))
            elif suffix == "status":
                dev = services.record_status(db, schemas.StatusIn.model_validate(payload))
                self._broadcast("status", schemas.DeviceOut.model_validate(dev))
            elif suffix == "ai":
                row = services.record_detection(db, schemas.DetectionIn.model_validate(payload))
                self._broadcast("detection", schemas.DetectionOut.model_validate(row))
            else:
                log.debug("Topic ignoré : %s", suffix)

    def _broadcast(self, kind: str, model) -> None:  # noqa: ANN001
        data = model.model_dump(mode="json")
        asyncio.run_coroutine_threadsafe(manager.broadcast(kind, data), self.loop)
