import os
import time
from jose import jwt, JWTError
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _pw_bytes_len(pw: str) -> int:
    return len(str(pw).encode("utf-8"))

def hash_password(password: str) -> str:
    if password is None:
        raise ValueError("Password required")

    password = str(password).strip()

    # bcrypt hard limit: 72 bytes
    if _pw_bytes_len(password) > 72:
        raise ValueError(f"Password too long: {_pw_bytes_len(password)} bytes (max 72)")

    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    if password is None:
        return False

    password = str(password).strip()

    if _pw_bytes_len(password) > 72:
        return False

    return pwd_context.verify(password, password_hash)

def create_access_token(subject: str) -> str:
    now = int(time.time())
    exp = now + ACCESS_TOKEN_EXPIRE_MIN * 60
    payload = {"sub": subject, "iat": now, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise ValueError("Invalid token")