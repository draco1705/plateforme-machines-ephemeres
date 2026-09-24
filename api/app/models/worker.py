from sqlalchemy import Column, Integer, String, DateTime, func, Index, CheckConstraint
from app.database import Base

class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (
        CheckConstraint("status IN ('AVAILABLE','BUSY','OFFLINE','MAINTENANCE')",
                        name="ck_workers_status"),
        CheckConstraint("cpu_used <= cpu_total", name="ck_workers_cpu"),
        CheckConstraint("ram_used_mb <= ram_total_mb", name="ck_workers_ram"),
    )
    id             = Column(Integer, primary_key=True)
    name           = Column(String(80), unique=True, nullable=False)
    ip             = Column(String(45), nullable=False)
    port           = Column(Integer, default=8001)     # port worker-agent
    cpu_total      = Column(Integer, default=2)
    ram_total_mb   = Column(Integer, default=2048)
    cpu_used       = Column(Integer, default=0)
    ram_used_mb    = Column(Integer, default=0)
    max_containers = Column(Integer, default=4)
    status         = Column(String(20), default="AVAILABLE")  # US14
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())
