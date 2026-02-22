from fastapi import APIRouter, HTTPException, Depends
from app.db import db_conn
from app.schemas import RegisterReq, LoginReq, TokenOut
from app.security import hash_password, verify_password, create_access_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(body: RegisterReq):
    # bcrypt max length guard (bytes)
    pw_len = len(body.password.encode("utf-8")) if isinstance(body.password, str) else -1
    if pw_len > 72:
        raise HTTPException(status_code=400, detail=f"Password too long: {pw_len} bytes (max 72)")

    pw_hash = hash_password(body.password)

    with db_conn() as conn:
        with conn.cursor() as cur:
            # unique checks
            cur.execute("SELECT 1 FROM users WHERE email=%s", (body.email,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email already exists")

            cur.execute("SELECT 1 FROM users WHERE client_id=%s", (body.client_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Client ID already exists")

            cur.execute(
                "INSERT INTO users (email, password_hash, role, client_id) VALUES (%s,%s,'client',%s)",
                (body.email, pw_hash, body.client_id),
            )
            conn.commit()

    return {"ok": True, "client_id": body.client_id, "email": body.email}


@router.post("/login", response_model=TokenOut)
def login(body: LoginReq):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, client_id FROM users WHERE email=%s", (body.email,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    password_hash, client_id = row[0], row[1]

    if not verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=client_id)  # sub = C001
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user