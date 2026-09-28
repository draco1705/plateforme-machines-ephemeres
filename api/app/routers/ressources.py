from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worker import Worker
from app.schemas.ressource import (
    RessourceUsage, RessourceSummary, RessourceReserveRequest, RessourceReleaseRequest,
)
from app.services.ressource_manager import RessourceManager
from app.core.deps import current_user
from app.schemas.ressource import WorkerStatusUpdate

VALID_TRANSITIONS = {
    "AVAILABLE":   {"BUSY", "OFFLINE", "MAINTENANCE"},
    "BUSY":        {"AVAILABLE", "OFFLINE"},          
    "OFFLINE":     {"AVAILABLE"},                     
    "MAINTENANCE": {"AVAILABLE"},                    
}

router = APIRouter()

@router.get("/", response_model=list[RessourceUsage])
def list_ressources(db: Session = Depends(get_db), _=Depends(current_user)):
    """lister les ressources disponibles par worker"""
    return db.query(Worker).order_by(Worker.id).all()

@router.get("/summary", response_model=RessourceSummary)
def summary(db: Session = Depends(get_db), _=Depends(current_user)):
    """resume global des ressources du cluster"""
    workers = db.query(Worker).all()
    return RessourceSummary(
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


@router.get("/{worker_id}", response_model=RessourceUsage)
def get_ressource(worker_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    w = db.get(Worker, worker_id)
    if not w:
        raise HTTPException(404, "Worker inconnu")
    return w


@router.post("/reserve", response_model=RessourceUsage, status_code=201)
def reserve(payload: RessourceReserveRequest, db: Session = Depends(get_db), _=Depends(current_user)):
    """reserver des ressources sur un worker (auto-select si worker_id=None)"""
    mgr = RessourceManager(db)
    worker = mgr.reserve(
        worker_id=payload.worker_id,
        cpu=payload.cpu,
        ram_mb=payload.ram_mb,
    )
    return worker


@router.post("/release", response_model=RessourceUsage)
def release(payload: RessourceReleaseRequest, db: Session = Depends(get_db), _=Depends(current_user)):
    """liberer des ressources"""
    mgr = RessourceManager(db)
    worker = mgr.release(
        worker_id=payload.worker_id,
        cpu=payload.cpu,
        ram_mb=payload.ram_mb,
    )
    return worker

@router.patch("/{worker_id}/status", response_model=RessourceUsage)
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