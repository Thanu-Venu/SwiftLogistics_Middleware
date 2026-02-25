from fastapi import APIRouter, Depends, HTTPException
from app.db import db_conn
from app.deps import get_current_user
import json
import time
from datetime import datetime, timezone

router = APIRouter(prefix="/orders", tags=["orders"])

def gen_order_id() -> str:
    return f"ORD-{int(time.time() * 1000)}"

def add_event(order_id: str, event_type: str, details: dict | None = None):
    details = details or {}
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO order_events(order_id, event_type, details) VALUES (%s,%s,%s::jsonb)",
                (order_id, event_type, json.dumps(details)),
            )
        conn.commit()

@router.post("")
@router.post("/")
def create_order(payload: dict, user=Depends(get_current_user)):
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=401, detail="client_id missing in token")

    order_id = gen_order_id()
    created_ms = int(time.time() * 1000)

    with db_conn() as conn:
        with conn.cursor() as cur:
            # orders.created_at BIGINT (epoch ms)
            cur.execute(
                """
                INSERT INTO orders (id, client_id, payload, status, retry_count, created_at, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, 0, %s, NOW())
                """,
                (order_id, client_id, json.dumps(payload), "NEW", created_ms),
            )

            # outbox schema: (aggregate_type, aggregate_id, event_type, payload)
            cur.execute(
                """
                INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                ("order", order_id, "ORDER_CREATED", json.dumps({"order_id": order_id})),
            )

        conn.commit()

    # audit trail (optional but good)
    try:
        add_event(order_id, "CREATED", {"client_id": client_id})
        add_event(order_id, "OUTBOX_ENQUEUED", {"event_type": "ORDER_CREATED"})
    except Exception:
        pass

    # UI-friendly: order is in DB, and outbox will publish soon
    return {"order_id": order_id, "status": "NEW"}

@router.get("/my")
def my_orders(user=Depends(get_current_user)):
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=401, detail="client_id missing in token")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, client_id, payload, status, created_at
                FROM orders
                WHERE client_id=%s
                ORDER BY created_at DESC
                """,
                (client_id,),
            )
            rows = cur.fetchall()

    orders = [
        {
            "id": r[0],
            "client_id": r[1],
            "payload": r[2],
            "status": r[3],
            "created_at": int(r[4]) if r[4] is not None else None,
            "created_at_iso": datetime.fromtimestamp(int(r[4]) / 1000, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            if r[4] is not None else None,
        }
        for r in rows
    ]

    return {"client_id": client_id, "orders": orders}