from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    fw: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    uptime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gas_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    motion: Mapped[bool] = mapped_column(Boolean, default=False)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heap_free: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    uptime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(8))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    source: Mapped[str] = mapped_column(String(16), default="esp")  # esp | api | ai


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cmd_id: Mapped[str] = mapped_column(String(32))
    actuator: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    frame_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_h: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    model: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    window_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
