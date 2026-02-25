# app/utils/events.py
import json
from app.db import db_conn

def log_event(order_id: str, event_type: str, details: dict | None = None):
    details = details or {}
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO order_events (order_id, event_type, details) VALUES (%s,%s,%s)",
                (order_id, event_type, json.dumps(details)),
            )
            conn.commit()