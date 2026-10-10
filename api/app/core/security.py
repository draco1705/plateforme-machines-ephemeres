from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.config import settings


def hash_password(p: str) -> str:
    pwd_bytes = p.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    pwd_bytes = p.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, h.encode("utf-8"))
    except Exception:
        return False

def create_token(user_id: int) -> str:
     payload = {
          "sub": str(user_id),
          "exp": datetime.now(UTC) + timedelta(minutes = settings.JWT_EXPIRE_MINUTES)
     }
     return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> int:
    data = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return int(data["sub"])