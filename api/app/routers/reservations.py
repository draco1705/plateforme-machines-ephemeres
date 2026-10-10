# app/routers/reservations.py
from datetime import UTC, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.machine import Machine
from app.models.reservation import Reservation
from app.models.reservation_event import ReservationEvent
from app.schemas.reservation import (
    ReservationCreate,
    ReservationEventOut,
    ReservationOut,
)
from app.services.reservation_events import log_event

router = APIRouter()

@router.post("", response_model=ReservationOut, status_code=201)
def create(payload: ReservationCreate, db: Session = Depends(get_db), user=Depends(current_user)):
    m = db.get(Machine, payload.machine_id)
    if not m or not m.enabled:
        raise HTTPException(404, "Machine indisponible")

    # verification des ressources minimum
    if payload.cpu < m.cpu_min or payload.ram_mb < m.ram_min_mb:
        raise HTTPException(400, f"Minimum: {m.cpu_min} CPU / {m.ram_min_mb} MB")

    # verification de la duree
    if not (5 <= payload.duration_minutes <= 8 * 60):
        raise HTTPException(400, "Durée entre 5 min et 8 h")

    # un seul lab actif par user 
    busy = db.query(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.status.in_(["PENDING", "RUNNING"]),
    ).first()
    if busy:
        raise HTTPException(409, "Vous avez déjà un lab actif")

    now = datetime.now(UTC)
    r = Reservation(
        user_id=user.id, machine_id=m.id,
        cpu=payload.cpu, ram_mb=payload.ram_mb,
        start_time=now,
        end_time=now + timedelta(minutes=payload.duration_minutes),
        status="PENDING",
    )
    db.add(r)
    db.flush()
    log_event(db, r.id, from_status=None, to_status="PENDING", reason="created_by_user")
    db.commit()
    db.refresh(r)
    return r

@router.get("", response_model=list[ReservationOut])
def list_mine(db: Session = Depends(get_db), user=Depends(current_user)):
    return db.query(Reservation).filter_by(user_id=user.id).order_by(Reservation.id.desc()).all()

@router.get("/{rid}", response_model=ReservationOut)
def get_one(rid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    r = db.get(Reservation, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404)
    return r

@router.delete("/{rid}", status_code=204)
def cancel(rid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    r = db.get(Reservation, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404)
    if r.status in ("EXPIRED", "CANCELLED"):
        raise HTTPException(409, "Déjà terminée")
    old_status = r.status
    r.status = "CANCELLED" 
    r.end_time = datetime.now(UTC)
    log_event(db, r.id, from_status=old_status, to_status="CANCELLED", reason="user_cancelled")
    db.commit()

@router.post("/{rid}/start", response_model=ReservationOut)
def start_reservation(rid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """redemarrer le conteneur une reservation."""
    r = db.get(Reservation, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404)
    if r.status != "RUNNING" or not r.container_id:
        raise HTTPException(409, "Réservation non active")
    # TODO appeler Worker Agent
    return r

@router.post("/{rid}/stop", response_model=ReservationOut)
def stop_reservation(rid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """arreter le conteneur sans le supprimer."""
    r = db.get(Reservation, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404)
    if r.status != "RUNNING":
        raise HTTPException(409, "Réservation non active")
    # TODO appeler Worker Agent
    return r

@router.get("/{rid}/events", response_model=list[ReservationEventOut])
def get_events(rid: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """voir l'historique complet d'une reservation."""
    r = db.get(Reservation, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404)

    events = (
        db.query(ReservationEvent)
        .filter_by(reservation_id=rid)
        .order_by(ReservationEvent.created_at.asc())
        .all()
    )
    return events