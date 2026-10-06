"""Logique métier partagée entre les routes HTTP et le pont MQTT."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models, schemas


def _now() -> datetime:
    return datetime.now(timezone.utc)


def touch_device(db: Session, device_id: str, *, online: bool | None = None,
                 ip: str | None = None, fw: str | None = None) -> models.Device:
    dev = db.get(models.Device, device_id)
    if dev is None:
        dev = models.Device(id=device_id, online=False)
        db.add(dev)
    dev.last_seen = _now()
    if online is not None:
        dev.online = online
    if ip:
        dev.ip = ip
    if fw:
        dev.fw = fw
    return dev


def record_telemetry(db: Session, data: schemas.TelemetryIn) -> models.Telemetry:
    row = models.Telemetry(**data.model_dump())
    db.add(row)
    touch_device(db, data.device_id, online=True)
    db.commit()
    db.refresh(row)
    return row


def record_alert(db: Session, data: schemas.AlertIn, source: str) -> models.Alert:
    row = models.Alert(**data.model_dump(), source=source)
    db.add(row)
    touch_device(db, data.device_id)
    db.commit()
    db.refresh(row)
    return row


def record_status(db: Session, data: schemas.StatusIn) -> models.Device:
    dev = touch_device(db, data.device_id, online=data.online, ip=data.ip, fw=data.fw)
    db.commit()
    db.refresh(dev)
    return dev


def record_command(db: Session, data: schemas.CommandIn, cmd_id: str, published: bool) -> models.Command:
    row = models.Command(**data.model_dump(), cmd_id=cmd_id, published=published)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_detection(db: Session, data: schemas.DetectionIn) -> models.Detection:
    row = models.Detection(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_prediction(db: Session, data: schemas.PredictionIn) -> models.Prediction:
    row = models.Prediction(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
