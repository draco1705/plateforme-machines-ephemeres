
from app.models.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session


class RessourceError(Exception):
    """ Erreur de gestion de ressources"""
    def __init__(self, message: str, code: str = "RESSOURCE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class RessourceManager:
     """ Gestion des reservations de ressources"""
     def __init__(self, db:Session):
          self.db = db 
     
     def select_worker(self, cpu:int, ram_mb: int) -> Worker | None:
          """ Choisit le worker AVAILABLE avec assez de ressources. 
          Strategie : "best fit" — worker le moins chargé en CPU"""
          stmt = (
               select(Worker)
               .where(
                    Worker.status == "AVAILABLE",
                    Worker.cpu_total - Worker.cpu_used >= cpu ,
                    Worker.ram_total_mb - Worker.ram_used_mb >= ram_mb,
                    Worker.container_count < Worker.max_containers,
               )
               .order_by(
                    (Worker.cpu_total - Worker.cpu_used).asc(),
                    Worker.id.asc(),
               )
               .limit(1)
               # eviter race condition
               .with_for_update(skip_locked = True)
          )
          return self.db.execute(stmt).scalar_one_or_none()

     def reserve(self, cpu: int, ram_mb: int, worker_id: int | None = None) -> Worker:
        """
        Reserve cpu + ram sur un worker.
        - Si worker_id donne: verifie que CE worker a assez, sinon 409.
        - Si worker_id=None: auto-select le meilleur worker, sinon 503.
        """
        if cpu <= 0 or ram_mb <= 0:
            raise RecursionError( "CPU et RAM doivent être > 0", "INVALID_INPUT")

        if worker_id is not None:
            worker = self.db.get(Worker, worker_id)
            if not worker:
                raise RecursionError("Worker inconnu", "WORKER_NOT_FOUND")
            if worker.status != "AVAILABLE":
                raise RecursionError(f"Worker en état {worker.status}", "WORKER_NOT_AVAILABLE")
            if worker.cpu_free < cpu or worker.ram_free_mb < ram_mb:
                raise RecursionError("Ressources insuffisantes sur ce worker", "INSUFFICIENT_RESSOURCES")
            if worker.can_accept <= 0:
                raise RecursionError("Nombre maximum de conteneurs atteint", "MAX_CONTAINERS")
        else:
            worker = self.select_worker(cpu, ram_mb)
            if worker is None:
                raise RecursionError("Aucun worker disponible — réessayez plus tard", "NO_WORKER")

        # appliquer la reservation
        worker.cpu_used       += cpu
        worker.ram_used_mb    += ram_mb
        worker.container_count += 1

        # mise à jour du statut
        if (worker.cpu_used >= worker.cpu_total
                or worker.ram_used_mb >= worker.ram_total_mb
                or worker.container_count >= worker.max_containers):
            worker.status = "BUSY"

        self.db.commit()
        self.db.refresh(worker)
        return worker

     def release(self, worker_id: int, cpu: int, ram_mb: int) -> Worker:
        """
        Libere cpu + ram sur un worker.
        Si worker.status == BUSY et qu'il redevient dispo → AVAILABLE.
        """
        worker = self.db.get(Worker, worker_id)
        if not worker:
            raise RessourceError("Worker inconnu", "WORKER_NOT_FOUND")

        if worker.cpu_used < cpu or worker.ram_used_mb < ram_mb:
            raise RessourceError("Release supérieur à ce qui est réservé", "INVALID_INPUT")
        
        if worker.container_count <= 0:
            raise RessourceError("Aucun conteneur a liberer", "NO_WORKER")

        worker.cpu_used        = max(0, worker.cpu_used - cpu)
        worker.ram_used_mb     = max(0, worker.ram_used_mb - ram_mb)
        worker.container_count = max(0, worker.container_count - 1)
        # transition BUSY → AVAILABLE si plus chargé
        if (worker.status == "BUSY" 
            and worker.cpu_used < worker.cpu_total
            and worker.ram_used_mb < worker.ram_total_mb
            and worker.container_count < worker.max_containers
        ):
            worker.status = "AVAILABLE"
        self.db.commit()
        self.db.refresh(worker)
        return worker