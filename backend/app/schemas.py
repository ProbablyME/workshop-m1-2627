"""Schémas Pydantic : ils reflètent docs/CONTRAT_DONNEES.md."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_DEVICE = "SX-G1-01"

AlertType = Literal["motion", "gas", "temperature", "humidity", "sensor_fault", "intrusion", "anomaly"]
Severity = Literal["info", "warning", "critical"]
Actuator = Literal["buzzer", "led_red", "led_green", "led", "camera"]  # camera : intrusion vue par l'IA (on/off)
Action = Literal["on", "off", "blink", "pulse"]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("ts", "last_seen", mode="after", check_fields=False)
    @classmethod
    def _force_utc(cls, v: datetime | None) -> datetime | None:
        """SQLite renvoie des datetimes naïfs : on les marque UTC pour que le JSON porte le 'Z'."""
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


# --- Télémétrie ---
class TelemetryIn(BaseModel):
    device_id: str = DEFAULT_DEVICE
    uptime_ms: int | None = None
    temperature: float | None = Field(default=None, ge=-40, le=85)
    humidity: float | None = Field(default=None, ge=0, le=100)
    gas_raw: int | None = Field(default=None, ge=0, le=1023)
    gas_ppm: float | None = Field(default=None, ge=0)
    motion: bool = False
    rssi: int | None = None
    heap_free: int | None = None


class TelemetryOut(TelemetryIn, _Out):
    id: int
    ts: datetime


# --- Alertes ---
class AlertIn(BaseModel):
    device_id: str = DEFAULT_DEVICE
    uptime_ms: int | None = None
    type: AlertType
    state: Literal["on", "off"] = "on"
    value: float | None = None
    severity: Severity = "warning"


class AlertOut(AlertIn, _Out):
    id: int
    ts: datetime
    source: str


# --- Statut boîtier ---
class StatusIn(BaseModel):
    device_id: str = DEFAULT_DEVICE
    online: bool
    ip: str | None = None
    fw: str | None = None


class DeviceOut(_Out):
    id: str
    online: bool
    ip: str | None
    fw: str | None
    last_seen: datetime | None


# --- Commandes ---
class CommandIn(BaseModel):
    device_id: str = DEFAULT_DEVICE
    actuator: Actuator
    action: Action
    duration_ms: int | None = Field(default=None, ge=0, le=60_000)


class CommandOut(CommandIn, _Out):
    id: int
    ts: datetime
    cmd_id: str
    published: bool


# --- IA ---
class DetectionIn(BaseModel):
    source: str = "yolo"
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[int] | None = Field(default=None, min_length=4, max_length=4)
    frame_w: int | None = None
    frame_h: int | None = None


class DetectionOut(DetectionIn, _Out):
    id: int
    ts: datetime


class PredictionIn(BaseModel):
    model: str = "isolation_forest"
    score: float
    is_anomaly: bool
    window_s: int | None = None
    features: dict[str, float] | None = None


class PredictionOut(PredictionIn, _Out):
    id: int
    ts: datetime


class Health(BaseModel):
    status: str
    mqtt_connected: bool
    db_ok: bool
    ws_clients: int
    version: str
