from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.models.machine import Machine
from app.models.reservation import Reservation
from app.models.worker import Worker
from app.services.container_manager import ContainerError, ContainerManager
from app.services.reservation_events import log_event
from app.services.ressource_manager import RessourceManager

WORKER_HEARTBEAT_TIMEOUT_SECONDS = 30


def check_and_auto_heal(batch_size: int = 10) -> int:
    """
    US43/US44: Détecte les conteneurs crashés (docker kill) ou les workers offline
    et auto-répare l'instance en la redémarrant / replanifiant.
    """
    db = SessionLocal()
    repaired_count = 0
    try:
        # 1. Marquer OFFLINE les workers dont le heartbeat est trop ancien (US43)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=WORKER_HEARTBEAT_TIMEOUT_SECONDS)
        db.query(Worker).filter(
            Worker.last_heartbeat < cutoff,
            Worker.status.notin_(["OFFLINE", "MAINTENANCE"])
        ).update({"status": "OFFLINE"}, synchronize_session=False)
        db.commit()

        # 2. Vérifier les réservations actives RUNNING
        stmt = (
            select(Reservation)
            .where(Reservation.status == "RUNNING")
            .limit(batch_size)
        )
        running = db.execute(stmt).scalars().all()
        if not running:
            return 0

        cmgr = ContainerManager()
        res_mgr = RessourceManager(db)

        for r in running:
            needs_repair = False
            repair_reason = ""

            worker = db.get(Worker, r.worker_id) if r.worker_id else None

            # Cas 1: Worker est devenu OFFLINE
            if worker and worker.status == "OFFLINE":
                needs_repair = True
                repair_reason = f"worker_{worker.name}_offline"

            # Cas 2: Conteneur arrêté / supprimé (docker kill)
            if not needs_repair and r.container_id:
                status = cmgr.get_container_status(worker, r.container_id)
                if status != "running":
                    needs_repair = True
                    repair_reason = f"container_dead_{status or 'not_found'}"

            if not needs_repair:
                continue

            print(f"[scheduler] Panne détectée sur #{r.id} ({repair_reason}) -> Déclenchement auto-réparation (US44)")
            log_event(db, r.id, from_status="RUNNING", to_status="RUNNING", reason=f"auto_repair_started: {repair_reason}")

            # Libérer les anciennes ressources sur le worker d'origine s'il existe
            if worker and worker.status != "OFFLINE":
                worker.cpu_used = max(0, worker.cpu_used - r.cpu)
                worker.ram_used_mb = max(0, worker.ram_used_mb - r.ram_mb)
                worker.container_count = max(0, worker.container_count - 1)

            # Replanifier sur un worker disponible
            new_worker = res_mgr.select_worker(r.cpu, r.ram_mb)
            machine = db.get(Machine, r.machine_id)
            if not machine:
                r.status = "FAILED"
                log_event(db, r.id, from_status="RUNNING", to_status="FAILED", reason="machine_template_missing")
                continue

            # Recréer le conteneur
            try:
                res = cmgr.create_container(new_worker, r, machine)
                new_container_id = res.get("container_id", "") if isinstance(res, dict) else str(res)
                r.container_id = new_container_id
                r.worker_id = new_worker.id if new_worker else None
                r.access_url = f"https://lab-{r.id}.lab.local"
                if new_worker:
                    new_worker.cpu_used += r.cpu
                    new_worker.ram_used_mb += r.ram_mb
                    new_worker.container_count += 1
                log_event(db, r.id, from_status="RUNNING", to_status="RUNNING", reason="auto_repaired_successfully")
                print(f"[scheduler] Auto-réparation réussie pour #{r.id} (nouveau conteneur: {new_container_id[:12]})")
                repaired_count += 1
            except ContainerError as e:
                print(f"[scheduler] Échec auto-réparation pour #{r.id}: {e.message}")

        db.commit()
    except Exception as e:
        print(f"[scheduler] ERREUR check_and_auto_heal: {e}")
        db.rollback()
    finally:
        db.close()
    return repaired_count
