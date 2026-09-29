from datetime import datetime, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.models.reservation import Reservation
from app.services.ressource_manager import RessourceError, RessourceManager
from app.services.container_manager import ContainerManager, ContainerError
from app.models.machine import Machine
from app.models.worker import Worker

def process_pending(batch_size: int = 10) -> int:
     "Traiter jusqu'a batch_size reservations PENDING"
     db = SessionLocal()
     processed = 0
     try:
          now = datetime.now(timezone.utc)
          stmt = (
               select(Reservation)
               .where(Reservation.status == "PENDING")
               .order_by(Reservation.start_time.asc())
               .limit(batch_size)
               .with_for_update(skip_locked=True)
          )
          pending = db.execute(stmt).scalars().all() 

          if not pending:
               return 0
          mgr = RessourceManager(db)
          try:
               cmgr = ContainerManager()
          except ContainerError as e:
               print(f"[scheduler] Docker indisponible: {e.message} — skip cycle")
               return 0

          for r in pending:
               # Reservation deja expiree avant meme d'etre traitee
               if r.end_time <= now:
                    r.status = "EXPIRED"
                    print(f"[scheduler] reservation #{r.id} PENDING -> EXPIRED (deja expiree)")
                    continue 
               worker = mgr.select_worker(r.cpu, r.ram_mb)
               if worker is None:
                    # Pas de ressource, reste PENDING (file d'attente)
                    print(f"[scheduler] reservation #{r.id} aucun worker disponible, reste PENDING")
                    continue

               machine = db.get(Machine, r.machine_id)
               if machine is None:
                    r.status = "FAILED"
                    print(f"[scheduler] reservation #{r.id} — machine introuvable")
                    continue
               # creer le conteneur Docker
               try:
                    container_id = cmgr.create_container(r, machine)
               except ContainerError as e:
                    print(f"[scheduler] reservation #{r.id} — création conteneur échouée: {e.message}")
                    r.status = "FAILED"
                    continue
               try:
                    worker.cpu_used += r.cpu
                    worker.ram_used_mb += r.ram_mb
                    worker.container_count += 1

                    if(worker.cpu_used >= worker.cpu_total or worker.ram_used_mb >= worker.ram_total_mb or worker.container_count >= worker.max_containers):
                         worker.status = "BUSY"
                    r.worker_id = worker.id
                    r.container_id = container_id
                    r.access_url = f"http://lab-{r.id}.lab.local"
                    r.status = "RUNNING"
                    print(
                         f"[scheduler] reservation #{r.id} PENDING → RUNNING "
                         f"(worker={worker.name}, cpu={r.cpu}, ram={r.ram_mb}MB)"
                    )
                    processed += 1

               except Exception as e:
                    print(f"[scheduler] ERREUR reservation #{r.id}: {e}")
                    r.status = "FAILED"
               db.commit()
     except Exception as e:
          print(f"[scheduler] ERREUR process_pending: {e}")
          db.rollback()
     finally:
          db.close()
     return processed