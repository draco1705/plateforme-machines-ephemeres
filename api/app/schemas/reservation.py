# app/schemas/reservation.py
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.common import ORMBase

ReservationStatus = Literal["PENDING", "RUNNING", "EXPIRED", "FAILED", "CANCELLED"]

class ReservationCreate(BaseModel):
    machine_id: int
    cpu: int = Field(ge=1, le=8)
    ram_mb: int = Field(ge=256, le=16384)
    duration_minutes: int = Field(ge=5, le=480)   # 5 min → 8h

class ReservationOut(ORMBase):
    id: int
    user_id: int
    machine_id: int
    worker_id: int | None
    container_id: str | None
    cpu: int
    ram_mb: int
    status: ReservationStatus
    start_time: datetime
    end_time: datetime
    access_url: str | None
    ssh_port: int | None

class ReservationSummary(ORMBase):
    id: int
    machine_id: int
    status: ReservationStatus
    end_time: datetime
    access_url: str | None

class ReservationEventOut(ORMBase):
    id: int
    reservation_id: int
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime