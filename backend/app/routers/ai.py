from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db
from ..security import require_api_key
from ..ws import manager

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/detections", response_model=schemas.DetectionOut, status_code=201,
             dependencies=[Depends(require_api_key)])
async def push_detection(body: schemas.DetectionIn, db: Session = Depends(get_db)):
    """Le script de vision (YOLO / OpenCV) pousse chaque détection de présence."""
    row = services.record_detection(db, body)
    out = schemas.DetectionOut.model_validate(row)
    await manager.broadcast("detection", out.model_dump(mode="json"))
    return out


@router.get("/detections", response_model=list[schemas.DetectionOut])
def list_detections(limit: int = Query(20, ge=1, le=500), db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Detection).order_by(models.Detection.ts.desc()).limit(limit)))


@router.post("/predictions", response_model=schemas.PredictionOut, status_code=201,
             dependencies=[Depends(require_api_key)])
async def push_prediction(body: schemas.PredictionIn, db: Session = Depends(get_db)):
    """Le modèle de maintenance prédictive pousse son score d'anomalie."""
    row = services.record_prediction(db, body)
    out = schemas.PredictionOut.model_validate(row)
    await manager.broadcast("prediction", out.model_dump(mode="json"))
    return out


@router.get("/predictions", response_model=list[schemas.PredictionOut])
def list_predictions(limit: int = Query(20, ge=1, le=500), db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Prediction).order_by(models.Prediction.ts.desc()).limit(limit)))
