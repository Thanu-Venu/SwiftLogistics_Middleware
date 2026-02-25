from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

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


def create_access_token(subject: str, role: str, email: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)

    payload = {
        "sub": subject,
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Invalid token")