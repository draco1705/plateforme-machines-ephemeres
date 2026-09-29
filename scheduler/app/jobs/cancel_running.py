from sqlalchemy import select
from app.database import SessionLocal
from app.models.reservation import Reservation
from app.models.worker import Worker
from app.services.container_manager import ContainerManager, ContainerError


def cancel_running(batch_size: int = 20) -> int:
    """Detruit les conteneurs des reservations CANCELLED and libere aussi les ressources."""
    db = SessionLocal()
    cleaned = 0
    try:
        stmt = (
            select(Reservation)
            .where(
                Reservation.status == "CANCELLED",
                Reservation.container_id.isnot(None),
            )
            .order_by(Reservation.id.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        to_clean = db.execute(stmt).scalars().all()

        if not to_clean:
            return 0
        try:
            cmgr = ContainerManager()
        except ContainerError as e:
            print(f"[scheduler] Docker indisponible: {e.message} — skip cancel")
            return 0

        for r in to_clean:
            # Detruire conteneur
            try:
                cmgr.remove_container(r.container_id)
            except ContainerError as e:
                print(f"[scheduler] cancel #{r.id} — remove échoué: {e.message}")

            # Liberer ressources
            if r.worker_id is not None:
                worker = db.get(Worker, r.worker_id)
                if worker is not None:
                    worker.cpu_used = max(0, worker.cpu_used - r.cpu)
                    worker.ram_used_mb = max(0, worker.ram_used_mb - r.ram_mb)
                    worker.container_count = max(0, worker.container_count - 1)
                    if worker.status == "BUSY" and worker.cpu_used < worker.cpu_total:
                        worker.status = "AVAILABLE"

            r.container_id = None
            r.access_url   = None
            cleaned += 1
            print(f"[scheduler] reservation #{r.id} CANCELLED → conteneur supprimé")

        db.commit()
    except Exception as e:
        print(f"[scheduler] ERREUR cancel_running: {e}")
        db.rollback()
    finally:
        db.close()

    return cleaned