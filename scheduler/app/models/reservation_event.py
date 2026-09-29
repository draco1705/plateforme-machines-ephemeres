from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Index
from app.database import Base


class ReservationEvent(Base):
    """ historique des changements de status d'une reservation, chaque transition (PENDING→RUNNING, RUNNING→EXPIRED, ...) cree une ligne."""
    __tablename__ = "reservation_events"
    __table_args__ = (
        Index("ix_reservation_events_reservation_id", "reservation_id"),
    )
    id = Column(Integer, primary_key=True)
    reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    reason = Column(String(255), nullable=True)   # "expired", "user_cancelled", "worker_failed"...
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)