from fastapi import APIRouter, Depends
from app.deps import require_roles
from app.db import db_conn

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats")
def stats(user=Depends(require_roles("admin"))):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM orders")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE status='NEW'")
            new = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE status='READY_FOR_DRIVER'")
            ready = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE status='DELIVERED'")
            delivered = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE status='FAILED'")
            failed = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE status='DLQ'")
            dlq = cur.fetchone()[0]

    return {"total": total, "new": new, "ready_for_driver": ready, "delivered": delivered, "failed": failed, "dlq": dlq}

@router.get("/orders")
def list_orders(status: str | None = None, user=Depends(require_roles("admin"))):
    q = "SELECT id, client_id, status, created_at FROM orders"
    params = []
    if status:
        q += " WHERE status=%s"
        params.append(status)
    q += " ORDER BY created_at DESC"

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(q, params)
            rows = cur.fetchall()

    return [{"id": r[0], "client_id": r[1], "status": r[2], "created_at": r[3]} for r in rows]

@router.get("/events/{order_id}")
def events(order_id: str, user=Depends(require_roles("admin"))):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, details, created_at
                FROM order_events
                WHERE order_id=%s
                ORDER BY created_at ASC
                """,
                (order_id,),
            )
            rows = cur.fetchall()
    return [{"event_type": r[0], "details": r[1], "created_at": str(r[2])} for r in rows]

@router.get("/outbox")
def outbox_pending(user=Depends(require_roles("admin"))):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, aggregate_type, aggregate_id, event_type
                FROM outbox
                ORDER BY id ASC
                LIMIT 200
                """
            )
            rows = cur.fetchall()

    return [{"id": r[0], "aggregate_type": r[1], "aggregate_id": r[2], "event_type": r[3]} for r in rows]