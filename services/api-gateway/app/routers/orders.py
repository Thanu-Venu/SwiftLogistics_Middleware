from fastapi import APIRouter, Depends
from app.db import db_conn
from app.deps import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])

@router.get("/my")
def my_orders(user=Depends(get_current_user)):
    # user["client_id"] is like C001
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, client_id, payload, status, created_at "
                "FROM orders WHERE client_id=%s ORDER BY created_at DESC",
                (user["client_id"],),
            )
            rows = cur.fetchall()

    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "client_id": r[1],
            "payload": r[2],
            "status": r[3],
            "created_at": r[4],
        })

    return {"client_id": user["client_id"], "orders": orders}