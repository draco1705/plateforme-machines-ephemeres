# app/models/reservation.py
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','EXPIRED','FAILED','CANCELLED')",
            name="ck_reservations_status",
        ),
        CheckConstraint("cpu >= 1", name="ck_reservations_cpu"),
        CheckConstraint("ram_mb >= 256", name="ck_reservations_ram"),
        CheckConstraint("end_time > start_time", name="ck_reservations_time"),
        # Index for Scheduler 
        Index("ix_reservations_status_end_time", "status", "end_time"),
        Index("ix_reservations_user_status", "user_id", "status"),
    )
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    machine_id   = Column(Integer, ForeignKey("machines.id"), nullable=False)
    worker_id    = Column(Integer, ForeignKey("workers.id"), nullable=True)  
    container_id = Column(String(100), nullable=True)
    cpu          = Column(Integer, nullable=False)
    ram_mb       = Column(Integer, nullable=False)
    status       = Column(String(20), default="PENDING")
    # PENDING | RUNNING | EXPIRED | FAILED | CANCELLED
    start_time   = Column(DateTime(timezone=True), server_default=func.now())
    end_time     = Column(DateTime(timezone=True), nullable=False)
    access_url   = Column(String(255), nullable=True)