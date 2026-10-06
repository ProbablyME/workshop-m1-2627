import secrets

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db
from ..security import require_api_key
from ..ws import manager

router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("", response_model=schemas.CommandOut, status_code=201, dependencies=[Depends(require_api_key)])
async def send_command(body: schemas.CommandIn, request: Request, db: Session = Depends(get_db)):
    """Panneau de contrôle : publie une commande vers l'ESP8266 sur <prefix>/cmd."""
    cmd_id = "c-" + secrets.token_hex(3)
    payload = {"cmd_id": cmd_id, **body.model_dump(exclude={"device_id"}, exclude_none=True)}
    published = request.app.state.mqtt.publish("cmd", payload)
    row = services.record_command(db, body, cmd_id, published)
    out = schemas.CommandOut.model_validate(row)
    await manager.broadcast("command", out.model_dump(mode="json"))
    return out


@router.get("", response_model=list[schemas.CommandOut])
def list_commands(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(models.Command).order_by(models.Command.ts.desc()).limit(limit)
    return list(db.scalars(stmt))
