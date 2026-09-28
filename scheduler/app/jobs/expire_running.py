from datetime import datetime, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.models.reservation import Reservation
from app.models.worker import Worker

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
          for r in expired:
               # Liberer les ressources du Worker
               if r.worker_id is not None:
                    worker = db.get(Worker, r.worker_id)
                    if worker is not None:
                         worker.cpu_used        = max(0, worker.cpu_used - r.cpu)
                         worker.ram_used_mb     = max(0, worker.ram_used_mb - r.ram_mb)
                         worker.container_count = max(0, worker.container_count - 1)
                         if worker.status == "BUSY" and worker.cpu_used < worker.cpu_total:
                              worker.status = "AVAILABLE"
               r.status       = "EXPIRED"
               r.container_id = None
               r.access_url   = None
               print(f"[scheduler] reservation #{r.id} RUNNING → EXPIRED (worker libéré)")
               expired_count += 1
          db.commit()
     except Exception as e:
          print(f"[scheduler] ERREUR expire_running: {e}")
          db.rollback()
     finally:
          db.close()
     return expired_count
