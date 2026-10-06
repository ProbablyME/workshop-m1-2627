from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db
from ..security import require_api_key
from ..ws import manager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=schemas.AlertOut, status_code=201, dependencies=[Depends(require_api_key)])
async def create_alert(body: schemas.AlertIn, db: Session = Depends(get_db)):
    """Point d'entrée obligatoire du sujet : réception d'un changement d'état capteur."""
    row = services.record_alert(db, body, source="api")
    out = schemas.AlertOut.model_validate(row)
    await manager.broadcast("alert", out.model_dump(mode="json"))
    return out


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    stmt = select(models.Alert).order_by(models.Alert.ts.desc()).limit(limit)
    return list(db.scalars(stmt))
