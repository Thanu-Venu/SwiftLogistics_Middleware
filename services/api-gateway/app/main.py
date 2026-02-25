import json
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import db_conn

# Routers
from app.routers.auth import router as auth_router
from app.routers.orders import router as orders_router
from app.routers.internal_cms import router as internal_cms_router
from app.routers.internal_ros import router as internal_ros_router
from app.routers.internal_wms import router as internal_wms_router
from app.routers.driver import router as driver_router
from app.routers.admin import router as admin_router  # ensure file exists

app = FastAPI(title="SwiftLogistics API Gateway")  # ✅ MUST be before any @app.*

# ---------------- Routers ----------------
app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(internal_cms_router)
app.include_router(internal_ros_router)
app.include_router(internal_wms_router)
app.include_router(driver_router)
app.include_router(admin_router)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="^http://.*:5173$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Helpers ----------------
def add_event(order_id: str, event_type: str, details: dict | None = None):
    details = details or {}
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO order_events(order_id, event_type, details) VALUES (%s,%s,%s::jsonb)",
                (order_id, event_type, json.dumps(details)),
            )
        conn.commit()

# ---------------- WebSocket ----------------
subscribers: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/orders/{order_id}")
async def ws_order(websocket: WebSocket, order_id: str):
    await websocket.accept()
    subscribers.setdefault(order_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if order_id in subscribers and websocket in subscribers[order_id]:
            subscribers[order_id].remove(websocket)

# ---------------- Driver WebSocket ----------------
driver_subscribers: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/driver/{driver_id}")
async def ws_driver(websocket: WebSocket, driver_id: str):
    await websocket.accept()
    driver_subscribers.setdefault(driver_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if driver_id in driver_subscribers and websocket in driver_subscribers[driver_id]:
            driver_subscribers[driver_id].remove(websocket)
# ---------------- Internal status update ----------------
class StatusUpdate(BaseModel):
    status: str

@app.post("/internal/orders/{order_id}/status")
async def internal_status(order_id: str, body: StatusUpdate):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status=%s, updated_at=NOW() WHERE id=%s",
                (body.status, order_id),
            )
            conn.commit()

    add_event(order_id, "STATUS_UPDATE", {"status": body.status})

    if order_id in subscribers:
        dead = []
        for ws in subscribers[order_id]:
            try:
                await ws.send_text(body.status)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                subscribers[order_id].remove(ws)
            except ValueError:
                pass

    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok"}


class DriverNotify(BaseModel):
    type: str
    order_id: str | None = None
    message: str | None = None
    payload: dict | None = None

@app.post("/internal/driver/{driver_id}/notify")
async def internal_notify_driver(driver_id: str, body: DriverNotify):
    msg = {
        "type": body.type,
        "order_id": body.order_id,
        "message": body.message,
        "payload": body.payload or {},
    }
    dead = []
    if driver_id in driver_subscribers:
        for ws in driver_subscribers[driver_id]:
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                driver_subscribers[driver_id].remove(ws)
            except ValueError:
                pass
    return {"ok": True}