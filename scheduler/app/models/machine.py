# app/models/machine.py
from app.database import Base
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, func


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (
        CheckConstraint("cpu_min >= 1", name="ck_machines_cpu_min"),
        CheckConstraint("ram_min_mb >= 256", name="ck_machines_ram_min"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_machines_port"),
    )
    id         = Column(Integer, primary_key=True)
    name       = Column(String(80), unique=True, nullable=False)   # "kali"
    image      = Column(String(200), nullable=False)               # "kalilinux/kali-rolling"
    cpu_min    = Column(Integer, default=1)
    ram_min_mb = Column(Integer, default=512)
    port       = Column(Integer, default=22)
    enabled    = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())