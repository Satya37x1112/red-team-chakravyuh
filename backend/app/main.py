"""VAJRAPRAHAAR FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api.central import router as central_router
from .api.integrations import router as integrations_router
from .api.routes import router
from .config import settings
from .db import init_db
from .telemetry.service import service
from .ws import hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    service.start()
    try:
        yield
    finally:
        await service.stop()


app = FastAPI(title="VAJRAPRAHAAR", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(integrations_router)
app.include_router(central_router)


@app.get("/")
def root() -> dict:
    return {"service": "VAJRAPRAHAAR", "telemetry_source": settings.telemetry_source}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await hub.connect(ws)
    # Push the latest snapshot immediately so a new client isn't blank.
    if service.latest is not None:
        await ws.send_json(
            {"type": "TELEMETRY_UPDATE", "payload": service.latest.model_dump(mode="json")}
        )
    try:
        while True:
            await ws.receive_text()  # ignore inbound; this channel is server->client
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)
