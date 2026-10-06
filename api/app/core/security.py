# api/app/core/security.py
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
     return pwd.hash(p)

def verify_password(p:str, h:str) -> bool:
     return pwd.verify(p, h)

def create_token(user_id: int) -> str:
     payload = {
          "sub": str(user_id),
          "exp": datetime.now(timezone.utc) + timedelta(minutes = settings.JWT_EXPIRE_MINUTES)
     }
     return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> int:
    data = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return int(data["sub"])