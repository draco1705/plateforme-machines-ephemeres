from pydantic import BaseModel
from app.schemas.common import ORMBase

class RessourceUsage(ORMBase):
     id: int 
     name: str 
     ip: str 
     status: str

     cpu_total: int
     cpu_used: int
     cpu_free: int

     ram_total_mb: int 
     ram_used_mb: int 
     ram_free_mb: int 

     max_containers: int 
     container_count: int 
     can_accept: int

class RessourceSummary(BaseModel):
    total_workers: int
    workers_available: int
    workers_busy: int
    workers_offline: int
    workers_maintenance: int

    total_cpu: int
    free_cpu: int

    total_ram_mb: int
    free_ram_mb: int

    total_containers_capacity: int
    containers_running: int

class RessourceReserveRequest(BaseModel):
    worker_id: int | None = None 
    cpu: int
    ram_mb: int

class RessourceReleaseRequest(BaseModel):
    worker_id: int
    cpu: int
    ram_mb: int

class WorkerStatusUpdate(BaseModel):
    status: str   # AVAILABLE | BUSY | OFFLINE | MAINTENANCE

