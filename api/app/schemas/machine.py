# app/schemas/machine.py
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.common import ORMBase

class MachineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    image: str = Field(min_length=3, max_length=200)
    cpu_min: int = Field(ge=1, le=8, default=1)
    ram_min_mb: int = Field(ge=256, le=16384, default=512)
    port: int = Field(ge=1, le=65535, default=22)
    enabled: bool = True

class MachineUpdate(BaseModel):
    name: str | None = None
    image: str | None = None
    cpu_min: int | None = Field(None, ge=1, le=8)
    ram_min_mb: int | None = Field(None, ge=256, le=16384)
    port: int | None = Field(None, ge=1, le=65535)
    enabled: bool | None = None

class MachineOut(ORMBase):
    id: int
    name: str
    image: str
    cpu_min: int
    ram_min_mb: int
    port: int
    enabled: bool
    created_at: datetime