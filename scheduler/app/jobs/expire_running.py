from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.database import SessionLocal
from app.models.reservation import Reservation
from app.models.worker import Worker
from app.services.container_manager import ContainerManager, ContainerError
from app.services.reservation_events import log_event 

MAX_PENDING_MINUTES = 30

def expire_running(batch_size: int = 20) -> int:
     """Expire jusqu'a batch_size reservations RUNNING. Retourne le nombre de reservations expirees."""
     db = SessionLocal()
     expired_count = 0
     try: 
          now = datetime.now(timezone.utc)
          stmt = (
               select(Reservation)
               .where(
                    Reservation.status == "RUNNING",
                    Reservation.end_time <= now,
               )
               .order_by(Reservation.end_time.asc())
               .limit(batch_size)
               .with_for_update(skip_locked=True)
          )
          expired = db.execute(stmt).scalars().all()
          if not expired:
               return 0
          try:
            cmgr = ContainerManager()
          except ContainerError as e:
            print(f"[scheduler] Docker indisponible: {e.message} — skip expire")
            return 0
          for r in expired:
               # supprimer le conteneur Docker
               if r.container_id and r.worker_id:
                    worker = db.get(Worker, r.worker_id)
                    if worker:
                         try:
                            cmgr.remove_container(worker, r.container_id)
                         except ContainerError as e:
                            print(f"[scheduler] remove échoué: {e.message}")
               # Liberer les ressources du Worker
               if r.worker_id is not None:
                    worker = db.get(Worker, r.worker_id)
                    if worker is not None:
                         worker.cpu_used = max(0, worker.cpu_used - r.cpu)
                         worker.ram_used_mb = max(0, worker.ram_used_mb - r.ram_mb)
                         worker.container_count = max(0, worker.container_count - 1)
                         if worker.status == "BUSY" and worker.cpu_used < worker.cpu_total:
                              worker.status = "AVAILABLE"
               old = r.status
               r.status       = "EXPIRED"
               r.container_id = None
               r.access_url   = None
               log_event(db, r.id, from_status=old, to_status="EXPIRED", reason="duration_elapsed")
               print(f"[scheduler] reservation #{r.id} RUNNING → EXPIRED (worker libéré)")
               expired_count += 1
          db.commit()
     except Exception as e:
          print(f"[scheduler] ERREUR expire_running: {e}")
          db.rollback()
     finally:
          db.close()
     return expired_count

def expire_pending_timeout() -> int:
    """Marque FAILED les réservations PENDING trop anciennes."""
    db = SessionLocal()
    count = 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=MAX_PENDING_MINUTES)
        stmt = (
            select(Reservation)
            .where(
                Reservation.status == "PENDING",
                Reservation.start_time < cutoff,
            )
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        stuck = db.execute(stmt).scalars().all()

        for r in stuck:
            old = r.status
            r.status = "FAILED"
            log_event(db, r.id, from_status=old, to_status="FAILED",
                      reason=f"pending_timeout_{MAX_PENDING_MINUTES}min")
            print(f"[scheduler] reservation #{r.id} PENDING → FAILED (timeout)")
            count += 1

        db.commit()
    except Exception as e:
        print(f"[scheduler] ERREUR expire_pending_timeout: {e}")
        db.rollback()
    finally:
        db.close()
    return count