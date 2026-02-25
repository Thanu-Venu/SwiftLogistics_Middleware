from fastapi import Header, HTTPException
from app.db import db_conn
from app.security import decode_token

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        client_id = payload.get("sub")
        if not client_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, role, client_id FROM users WHERE client_id=%s",
                (client_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": row[0],
        "email": row[1],
        "role": row[2],
        "client_id": row[3],
    }