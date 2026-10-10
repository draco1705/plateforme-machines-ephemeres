# app/schemas/user.py
import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMBase


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=80)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.fullmatch(pattern, value):
            raise ValueError("Invalid email format")
        return value

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