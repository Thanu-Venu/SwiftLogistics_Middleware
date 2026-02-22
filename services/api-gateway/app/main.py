import json
import os
import time
import requests
import socket
from app.db import db_conn
from app.routers.auth import router as auth_router
from app.routers.orders import router as orders_router
from typing import Dict, List
from fastapi.middleware.cors import CORSMiddleware

import pika
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

RABBIT_URL = os.getenv("RABBIT_URL")
CMS_URL = os.getenv("CMS_URL", "http://cms-soap:9000/soap")
ROS_URL = os.getenv("ROS_URL", "http://ros-rest:9100/optimize-route")
WMS_HOST = os.getenv("WMS_HOST", "wms-tcp")
WMS_PORT = int(os.getenv("WMS_PORT", "9200"))

app = FastAPI(title="SwiftLogistics API Gateway")

app.include_router(auth_router)
app.include_router(orders_router)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://.*:5173$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simple in-memory WS subscribers (demo) ---
subscribers: Dict[str, List[WebSocket]] = {}


def init_db():
    with db_conn() as conn:
        with conn.cursor() as cur:
            # orders table (already)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    status TEXT NOT NULL,
                    created_at BIGINT NOT NULL
                );
                """
            )
            # users table
            cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'client',
                    client_id TEXT NOT NULL UNIQUE,
                    created_at BIGINT NOT NULL DEFAULT (extract(epoch from now())::bigint)
                );
                """
            )
            conn.commit()

def publish_order_created(order_id: str, client_id: str, payload: dict):
    params = pika.URLParameters(RABBIT_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue="order.created", durable=True)

    msg = {"order_id": order_id, "client_id": client_id, "payload": payload}
    channel.basic_publish(
        exchange="",
        routing_key="order.created",
        body=json.dumps(msg).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),  # persistent
    )
    connection.close()


class CreateOrderReq(BaseModel):
    items: list
    destination: str


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"ok": True}


from fastapi import Depends
from app.deps import get_current_user

@app.post("/orders")
def create_order(req: CreateOrderReq, user=Depends(get_current_user)):
    order_id = f"ORD-{int(time.time()*1000)}"
    created_at = int(time.time())

    client_id = user["client_id"]  # ✅ from JWT

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (id, client_id, payload, status, created_at) VALUES (%s,%s,%s,%s,%s)",
                (order_id, client_id, json.dumps(req.dict()), "PENDING", created_at),
            )
            conn.commit()

    publish_order_created(order_id, client_id, req.dict())
    return {"order_id": order_id, "status": "PENDING"}

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, client_id, payload, status, created_at FROM orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
    if not row:
        return {"error": "not_found"}
    return {"id": row[0], "client_id": row[1], "payload": row[2], "status": row[3], "created_at": row[4]}


@app.websocket("/ws/orders/{order_id}")
async def ws_order(websocket: WebSocket, order_id: str):
    await websocket.accept()
    subscribers.setdefault(order_id, []).append(websocket)
    try:
        while True:
            # keep alive (client can send pings)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        subscribers.get(order_id, []).remove(websocket)


# Worker will call this to push realtime updates (simple + demo-friendly)
class StatusUpdate(BaseModel):
    status: str


@app.post("/internal/orders/{order_id}/status")
async def internal_status(order_id: str, body: StatusUpdate):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status=%s WHERE id=%s", (body.status, order_id))
            conn.commit()

    # push to websocket subscribers
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

@app.post("/internal/cms/soap")
def internal_cms_soap(payload: dict):
    """
    UI -> api-gateway -> CMS SOAP mock
    payload: { "order_id": "ORD-...", "client_id": "C001" }
    """
    order_id = payload.get("order_id", "ORD-DEMO")
    client_id = payload.get("client_id", "C001")

    xml = f"""<?xml version="1.0"?>
<Envelope>
  <Body>
    <CreateOrder>
      <OrderId>{order_id}</OrderId>
      <ClientId>{client_id}</ClientId>
    </CreateOrder>
  </Body>
</Envelope>
"""
    r = requests.post(CMS_URL, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml"}, timeout=5)
    return {"status_code": r.status_code, "response_xml": r.text}


@app.post("/internal/ros/optimize")
def internal_ros_optimize(payload: dict):
    """
    UI -> api-gateway -> ROS REST mock
    payload: { "order_id": "ORD-..." }
    """
    r = requests.post(ROS_URL, json=payload, timeout=5)
    return {"status_code": r.status_code, "response_json": r.json()}


@app.post("/internal/wms/send")
def internal_wms_send(payload: dict):
    """
    UI -> api-gateway -> WMS TCP mock
    payload: { "message": "ADD_PACKAGE|ORD-..." }
    """
    message = (payload.get("message") or "ADD_PACKAGE|ORD-DEMO").strip() + "\n"
    with socket.create_connection((WMS_HOST, WMS_PORT), timeout=5) as s:
        s.sendall(message.encode("utf-8"))
        data = s.recv(1024).decode("utf-8", errors="ignore").strip()
    return {"reply": data}