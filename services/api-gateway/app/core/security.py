from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(*, subject: str, secret: str, alg: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, secret, algorithm=alg)

def decode_token(token: str, secret: str, alg: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[alg])
    except JWTError as e:
        raise ValueError("Invalid token") from e