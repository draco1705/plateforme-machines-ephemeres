from app.models.reservation_event import ReservationEvent
from sqlalchemy.orm import Session


def log_event(
    db: Session,
    reservation_id: int,
    from_status: str | None,
    to_status: str,
    reason: str | None = None,
) -> ReservationEvent:
    """ajoute un event à l'historique d'une reservation."""
    event = ReservationEvent(
        reservation_id=reservation_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )
    db.add(event)
    return event