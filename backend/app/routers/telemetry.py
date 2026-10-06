from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db
from ..security import require_api_key
from ..ws import manager

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latest", response_model=schemas.TelemetryOut)
def latest(db: Session = Depends(get_db)):
    row = db.scalars(select(models.Telemetry).order_by(models.Telemetry.ts.desc()).limit(1)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Aucune mesure reçue")
    return row


@router.get("", response_model=list[schemas.TelemetryOut])
def history(
    minutes: int = Query(30, ge=1, le=24 * 60),
    limit: int = Query(1000, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    stmt = (
        select(models.Telemetry)
        .where(models.Telemetry.ts >= since)
        .order_by(models.Telemetry.ts.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.post("", response_model=schemas.TelemetryOut, status_code=201, dependencies=[Depends(require_api_key)])
async def ingest_http(body: schemas.TelemetryIn, db: Session = Depends(get_db)):
    """Ingestion HTTP de secours (tests sans broker). Le chemin nominal reste MQTT."""
    row = services.record_telemetry(db, body)
    out = schemas.TelemetryOut.model_validate(row)
    await manager.broadcast("telemetry", out.model_dump(mode="json"))
    return out
