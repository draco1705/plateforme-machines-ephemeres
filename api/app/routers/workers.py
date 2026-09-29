# app/routers/workers.py
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worker import Worker
from app.schemas.worker import WorkerRegister, WorkerHeartbeat, WorkerOut
from app.core.deps import current_user

router = APIRouter()

@router.post("/register", response_model=WorkerOut, status_code=201)
def register(payload: WorkerRegister, db: Session = Depends(get_db)):
    w = db.query(Worker).filter_by(name=payload.name).first()
    if w:
        # upsert: worker reboot, update infor user
        for k, v in payload.model_dump().items():
            setattr(w, k, v)
    else:
        w = Worker(**payload.model_dump())
        db.add(w)
    w.status = "AVAILABLE"
    w.last_heartbeat = datetime.now(timezone.utc)
    db.commit(); db.refresh(w)
    return w

@router.post("/heartbeat", status_code=204)
def heartbeat(payload: WorkerHeartbeat, db: Session = Depends(get_db)):
    w = db.query(Worker).filter_by(name=payload.name).first()
    if not w: raise HTTPException(404, "Worker non enregistré")
    w.cpu_used      = payload.cpu_used
    w.ram_used_mb   = payload.ram_used_mb
    w.last_heartbeat = datetime.now(timezone.utc)
    # US07 : detection des Workers indisponibles
    w.status = "BUSY" if w.cpu_used >= w.cpu_total else "AVAILABLE"
    db.commit()

@router.get("", response_model=list[WorkerOut])
def list_workers(db: Session = Depends(get_db), _=Depends(current_user)):
    _mark_offline(db)
    return db.query(Worker).all()

@router.get("/{wid}", response_model=WorkerOut)
def get_worker(wid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    w = db.get(Worker, wid)
    if not w: raise HTTPException(404)
    return w

def _mark_offline(db: Session, timeout_s: int = 30):
    pass
    # cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_s)
    # db.query(Worker).filter(Worker.last_heartbeat < cutoff)\
    #                 .update({"status": "OFFLINE"})
    # db.commit()