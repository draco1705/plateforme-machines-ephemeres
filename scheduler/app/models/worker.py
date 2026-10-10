from app.database import Base
from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, func


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (
        CheckConstraint("status IN ('AVAILABLE','BUSY','OFFLINE','MAINTENANCE')", name="ck_workers_status"),
        CheckConstraint("cpu_used >= 0 AND cpu_used <= cpu_total", name="ck_workers_cpu"),
        CheckConstraint("ram_used_mb >= 0 AND ram_used_mb <= ram_total_mb", name="ck_workers_ram"),
        CheckConstraint("container_count >= 0 AND container_count <= max_containers", name="ck_workers_containers"),
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
    container_count= Column(Integer, nullable=False, default=0)
    status         = Column(String(20), default="AVAILABLE") 
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def cpu_free(self)->int:
        return self.cpu_total - self.cpu_used

    @property
    def ram_free_mb(self) -> int:
        return self.ram_total_mb - self.ram_used_mb
    
    @property
    def can_accept(self) -> int:
        return self.max_containers - self.container_count