from fastapi import APIRouter, Depends
from app.db import db_conn
from app.deps import get_current_user

import json
import time

from datetime import datetime, timezone

def ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

router = APIRouter(prefix="/orders", tags=["orders"])


def gen_order_id() -> str:
    return f"ORD-{int(time.time() * 1000)}"


@router.post("/")
@router.post("")   # handles /orders
@router.post("/")  # handles /orders/
def create_order(payload: dict, user=Depends(get_current_user)):
    client_id = user.get("client_id") or user.get("sub") or user.get("username")
    if not client_id:
        return {"error": "client_id missing in token/user"}

    order_id = gen_order_id()
    created_ms = int(time.time() * 1000)

    with db_conn() as conn:
        with conn.cursor() as cur:
            # created_at is BIGINT, updated_at is TIMESTAMPTZ
            cur.execute(
                """
                INSERT INTO orders (id, client_id, payload, status, retry_count, created_at, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, 0, %s, NOW())
                """,
                (order_id, client_id, json.dumps(payload), "NEW", created_ms),
            )

            # outbox.created_at type might be TIMESTAMPTZ (most likely) -> use NOW()
            cur.execute(
                """
                INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload, published, created_at)
                VALUES (%s, %s, %s, %s::jsonb, FALSE, NOW())
                """,
                ("order", order_id, "ORDER_CREATED", json.dumps({"order_id": order_id})),
            )

        conn.commit()

    return {"order_id": order_id, "status": "QUEUED"}

@router.get("/my")
def my_orders(user=Depends(get_current_user)):
    client_id = user.get("client_id") or user.get("sub") or user.get("username")

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
        "created_at": int(r[4]) if r[4] is not None else None,  # ✅ epoch ms (number)
        "created_at_iso": datetime.fromtimestamp(int(r[4]) / 1000, tz=timezone.utc)
                          .isoformat(timespec="milliseconds")
                          if r[4] is not None else None,          # ✅ parse-safe string
    }
    for r in rows
]

    return {"client_id": client_id, "orders": orders}