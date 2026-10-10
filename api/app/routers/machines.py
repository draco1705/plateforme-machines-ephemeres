# app/routers/machines.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.machine import Machine
from app.schemas.machine import MachineCreate, MachineOut

router = APIRouter()

@router.get("", response_model=list[MachineOut])
def list_machines(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.query(Machine).filter_by(enabled=True).all()

@router.get("/{mid}", response_model=MachineOut)
def get_machine(mid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    m = db.get(Machine, mid)
    if not m:
        raise HTTPException(404, "Machine inconnue")
    return m

@router.post("", response_model=MachineOut, status_code=201)
def create_machine(payload: MachineCreate, db: Session = Depends(get_db), user=Depends(current_user)):
    m = Machine(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

@router.delete("/{mid}", status_code=204)
def delete_machine(mid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    m = db.get(Machine, mid)
    if not m:
        raise HTTPException(404, "Machine inconnue")
    m.enabled = False  
    db.commit()

@router.post("/{mid}/start", status_code=202)
def start_machine(mid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    m = db.get(Machine, mid)
    if not m:
        raise HTTPException(404, "Machine inconnue")
    return {"status": "started", "machine_id": mid}

@router.post("/{mid}/stop", status_code=202)
def stop_machine(mid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    m = db.get(Machine, mid)
    if not m:
        raise HTTPException(404, "Machine inconnue")
    return {"status": "stopped", "machine_id": mid}