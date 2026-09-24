# app/schemas/user.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.schemas.common import ORMBase

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=80)

class UserOut(ORMBase):
    id: int
    email: EmailStr
    role: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: int          # user_id
    exp: datetime