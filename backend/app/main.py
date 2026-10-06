import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import schemas
from .config import settings
from .db import engine, init_db
from .mqtt_client import MqttBridge
from .routers import ai, alerts, commands, devices, telemetry
from .ws import manager

VERSION = "0.1.0"

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bridge = MqttBridge(loop=asyncio.get_running_loop())
    bridge.start()
    app.state.mqtt = bridge
    log.info("Sentinel-X API %s démarrée", VERSION)
    yield
    bridge.stop()


app = FastAPI(
    title="Sentinel-X API",
    description="Centre de Commandement Tactique — AetherCorp Industrial Solutions (Groupe 1)",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
for r in (alerts.router, telemetry.router, commands.router, devices.router, ai.router):
    app.include_router(r, prefix=API)


@app.get(f"{API}/health", response_model=schemas.Health, tags=["system"])
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    mqtt_ok = bool(getattr(app.state, "mqtt", None) and app.state.mqtt.connected)
    return schemas.Health(
        status="ok" if (db_ok and mqtt_ok) else "degraded",
        mqtt_connected=mqtt_ok,
        db_ok=db_ok,
        ws_clients=manager.count,
        version=VERSION,
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Flux temps réel pour le dashboard. Le client n'envoie rien d'utile (ping éventuel)."""
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
