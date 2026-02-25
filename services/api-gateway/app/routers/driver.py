from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.db import db_conn
from app.deps import require_roles
import json
import requests
import os
import base64
from typing import Any

router = APIRouter(prefix="/driver", tags=["driver"])

API_INTERNAL_NOTIFY = os.getenv(
    "API_INTERNAL_NOTIFY",
    "http://api-gateway:8000/internal/driver/{driver_id}/notify"
)

# ---------------- Schemas ----------------
class DriverStatusUpdate(BaseModel):
    status: str  # "DELIVERED" or "FAILED" (you can add OUT_FOR_DELIVERY later)
    reason: str | None = None

class ProofUpload(BaseModel):
    proof_type: str  # "photo" or "signature"
    data_base64: str  # base64 or data-url
    meta: dict | None = None

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

def get_driver_user_id(email: str) -> str:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s AND role='driver'", (email,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Driver not found")
    return row[0]

def ensure_my_order(order_id: str, driver_id: str) -> dict:
    """
    Returns the order row fields we may need.
    Also ensures assigned_driver_id matches.
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, assigned_driver_id, payload, status FROM orders WHERE id=%s",
                (order_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    if row[1] != driver_id:
        raise HTTPException(status_code=403, detail="Not your order")

    return {"id": row[0], "assigned_driver_id": row[1], "payload": row[2], "status": row[3]}

def notify_driver(driver_id: str, payload: dict):
    # best effort
    try:
        requests.post(
            API_INTERNAL_NOTIFY.format(driver_id=driver_id),
            json=payload,
            timeout=2,
        )
    except Exception:
        pass

def normalize_payload(p: Any) -> dict:
    """
    Postgres jsonb via psycopg2 is typically dict already.
    But sometimes could be str.
    """
    if p is None:
        return {}
    if isinstance(p, dict):
        return p
    if isinstance(p, str):
        try:
            v = json.loads(p)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}

def strip_data_url(b64: str) -> str:
    # allow both raw base64 and data URL
    if not b64:
        return ""
    s = b64.strip()
    if s.startswith("data:"):
        # data:image/png;base64,AAAA...
        parts = s.split(",", 1)
        if len(parts) == 2:
            return parts[1].strip()
    return s

def base64_size_ok(b64: str, max_bytes: int) -> bool:
    """
    base64 expands ~4/3, so decode size check.
    """
    try:
        raw = base64.b64decode(b64, validate=False)
        return len(raw) <= max_bytes
    except Exception:
        return False

# ---------------- APIs ----------------

@router.get("/orders")
def my_driver_orders(user=Depends(require_roles("driver"))):
    driver_id = get_driver_user_id(user["email"])

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, client_id, payload, status, created_at, updated_at
                FROM orders
                WHERE assigned_driver_id=%s
                ORDER BY created_at DESC
                """,
                (driver_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "id": o[0],
            "client_id": o[1],
            "payload": o[2],
            "status": o[3],
            "created_at": o[4],
            "updated_at": str(o[5]) if o[5] is not None else None,
        }
        for o in rows
    ]

# ✅ Manifest for today (PoC)
@router.get("/manifest/today")
def manifest_today(user=Depends(require_roles("driver"))):
    driver_id = get_driver_user_id(user["email"])

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, client_id, payload, status, created_at, updated_at
                FROM orders
                WHERE assigned_driver_id=%s
                  AND status IN ('READY_FOR_DRIVER','OUT_FOR_DELIVERY')
                ORDER BY created_at ASC
                """,
                (driver_id,),
            )
            rows = cur.fetchall()

    items = []
    for r in rows:
        payload = normalize_payload(r[2])
        items.append(
            {
                "id": r[0],
                "client_id": r[1],
                "status": r[3],
                "created_at": r[4],
                "updated_at": str(r[5]) if r[5] is not None else None,
                "destination": payload.get("destination"),
                "items": payload.get("items"),
                "route": payload.get("route"),
            }
        )

    return {"driver_id": driver_id, "orders": items}

@router.post("/orders/{order_id}/status")
def update_delivery(order_id: str, body: DriverStatusUpdate, user=Depends(require_roles("driver"))):
    if body.status not in ("DELIVERED", "FAILED"):
        raise HTTPException(status_code=400, detail="Invalid status")

    if body.status == "FAILED" and (not body.reason or not body.reason.strip()):
        raise HTTPException(status_code=400, detail="Reason required for FAILED")

    driver_id = get_driver_user_id(user["email"])
    ensure_my_order(order_id, driver_id)

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE orders
                SET status=%s, updated_at=NOW(), last_error=%s
                WHERE id=%s
                """,
                (body.status, body.reason, order_id),
            )
        conn.commit()

    add_event(order_id, body.status, {"driver_id": driver_id, "reason": body.reason})

    notify_driver(
        driver_id,
        {"type": "STATUS_UPDATED", "order_id": order_id, "payload": {"status": body.status}},
    )
    return {"ok": True}

# ✅ Proof upload (photo/signature)
@router.post("/orders/{order_id}/proof")
def upload_proof(order_id: str, body: ProofUpload, user=Depends(require_roles("driver"))):
    if body.proof_type not in ("photo", "signature"):
        raise HTTPException(status_code=400, detail="Invalid proof_type")

    driver_id = get_driver_user_id(user["email"])
    ensure_my_order(order_id, driver_id)

    b64 = strip_data_url(body.data_base64)

    # size guard (PoC): 500KB for signature, 2MB for photo
    max_bytes = 2 * 1024 * 1024 if body.proof_type == "photo" else 500 * 1024
    if not b64 or len(b64) < 50:
        raise HTTPException(status_code=400, detail="Proof data too small")

    if not base64_size_ok(b64, max_bytes=max_bytes):
        raise HTTPException(status_code=400, detail=f"Proof too large (max {max_bytes} bytes)")

    add_event(
        order_id,
        "PROOF_UPLOADED",
        {
            "driver_id": driver_id,
            "proof_type": body.proof_type,
            "meta": body.meta or {},
            "data_base64": b64,  # PoC storage (not for prod)
        },
    )

    notify_driver(
        driver_id,
        {"type": "PROOF_UPLOADED", "order_id": order_id, "payload": {"proof_type": body.proof_type}},
    )
    return {"ok": True}