from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worker import Worker
from app.schemas.resource import (
    ResourceUsage, ResourceSummary, ResourceReserveRequest, ResourceReleaseRequest,
)
from app.services.resource_manager import ResourceManager
from app.core.deps import current_user
from app.schemas.resource import WorkerStatusUpdate

VALID_TRANSITIONS = {
    "AVAILABLE":   {"BUSY", "OFFLINE", "MAINTENANCE"},
    "BUSY":        {"AVAILABLE", "OFFLINE"},          
    "OFFLINE":     {"AVAILABLE"},                     
    "MAINTENANCE": {"AVAILABLE"},                    
}

router = APIRouter()

@router.get("/", response_model=list[ResourceUsage])
def list_resources(db: Session = Depends(get_db), _=Depends(current_user)):
    """lister les ressources disponibles par worker"""
    return db.query(Worker).order_by(Worker.id).all()

@router.get("/summary", response_model=ResourceSummary)
def summary(db: Session = Depends(get_db), _=Depends(current_user)):
    """resume global des ressources du cluster"""
    workers = db.query(Worker).all()
    return ResourceSummary(
        total_workers=len(workers),
        workers_available=sum(1 for w in workers if w.status == "AVAILABLE"),
        workers_busy=sum(1 for w in workers if w.status == "BUSY"),
        workers_offline=sum(1 for w in workers if w.status == "OFFLINE"),
        workers_maintenance=sum(1 for w in workers if w.status == "MAINTENANCE"),
        total_cpu=sum(w.cpu_total for w in workers),
        free_cpu=sum(w.cpu_free for w in workers),
        total_ram_mb=sum(w.ram_total_mb for w in workers),
        free_ram_mb=sum(w.ram_free_mb for w in workers),
        total_containers_capacity=sum(w.max_containers for w in workers),
        containers_running=sum(w.container_count for w in workers),
    )


@router.get("/{worker_id}", response_model=ResourceUsage)
def get_resource(worker_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    w = db.get(Worker, worker_id)
    if not w:
        raise HTTPException(404, "Worker inconnu")
    return w


@router.post("/reserve", response_model=ResourceUsage, status_code=201)
def reserve(payload: ResourceReserveRequest, db: Session = Depends(get_db), _=Depends(current_user)):
    """reserver des ressources sur un worker (auto-select si worker_id=None)"""
    mgr = ResourceManager(db)
    worker = mgr.reserve(
        worker_id=payload.worker_id,
        cpu=payload.cpu,
        ram_mb=payload.ram_mb,
    )
    return worker


@router.post("/release", response_model=ResourceUsage)
def release(payload: ResourceReleaseRequest, db: Session = Depends(get_db), _=Depends(current_user)):
    """liberer des ressources"""
    mgr = ResourceManager(db)
    worker = mgr.release(
        worker_id=payload.worker_id,
        cpu=payload.cpu,
        ram_mb=payload.ram_mb,
    )
    return worker

@router.patch("/{worker_id}/status", response_model=ResourceUsage)
def update_status(worker_id: int, payload: WorkerStatusUpdate, db: Session = Depends(get_db), user = Depends(current_user)):
     """mettre a jour manellement le status (admin only)"""
     if user.role != "admin":
          raise HTTPException(403, "Admin requis")
     w = db.get(Worker, worker_id)
     if not w:
          raise HTTPException(404, "Worker inconnu")
     if payload.status not in VALID_TRANSITIONS.get(w.status, set()):
          raise HTTPException(409, f"Transition invalide: {w.status} -> {payload.status}")
     w.status = payload.status
     db.commit()
     db.refresh(w)
     return w 