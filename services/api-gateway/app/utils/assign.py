from app.db import db_conn

def pick_driver_user_id() -> str | None:
    # simplest: pick first driver (later you can do round-robin)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE role='driver' ORDER BY email LIMIT 1")
            row = cur.fetchone()
    return row[0] if row else None