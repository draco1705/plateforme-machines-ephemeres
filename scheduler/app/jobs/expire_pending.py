from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.reservation import Reservation
from app.services.reservation_events import log_event
from sqlalchemy import select

MAX_PENDING_MINUTES = 30

def expire_pending_timeout() -> int:
     """marque FAILED les reservations PENDING trop anciennes."""
     db = SessionLocal()
     count=0
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
               log_event(db, r.id, from_status=old, to_status="FAILED", reason=f"pending_timeout_{MAX_PENDING_MINUTES}min")
               print(f"[scheduler] reservation #{r.id} PENDING -> FAILED (timeout)")
               count+=1
          db.commit()
     except Exception as e:
          print(f"[scheduler] ERREUR expire_pending_timeout: {e}")
          db.rollback()
     finally:
          db.close()
     return count
