# app/schemas/worker.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase

WorkerStatus = Literal["AVAILABLE", "BUSY", "OFFLINE", "MAINTENANCE"]

class WorkerRegister(BaseModel):
    """Body de POST /workers/register"""
    name: str = Field(min_length=2, max_length=80)
    ip: str = Field(min_length=7, max_length=45)   # IPv4 or IPv6
    port: int = Field(ge=1, le=65535, default=8001)
    cpu_total: int = Field(ge=1, le=64)
    ram_total_mb: int = Field(ge=512)
    max_containers: int = Field(ge=1, le=100, default=4)

class WorkerHeartbeat(BaseModel):
    """Body de POST /workers/heartbeat """
    name: str
    cpu_used: int = Field(ge=0)
    ram_used_mb: int = Field(ge=0)

class WorkerOut(ORMBase):
    """Response de GET /workers, GET /workers/{id}"""
    id: int
    name: str
    ip: str
    port: int
    cpu_total: int
    cpu_used: int
    ram_total_mb: int
    ram_used_mb: int
    max_containers: int
    status: WorkerStatus
    last_heartbeat: datetime