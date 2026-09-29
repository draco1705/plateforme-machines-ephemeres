import docker
from docker.errors import DockerException, ImageNotFound, APIError

from app.models.reservation import Reservation
from app.models.machine import Machine
from app.models.worker import Worker

class ContainerError(Exception):
    """Erreur de gestion de conteneur."""
    def __init__(self, message: str, code: str = "CONTAINER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ContainerManager:
    """Gere le cycle de vie des conteneurs lab."""
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()   
        except DockerException as e:
            raise ContainerError(f"Docker indisponible: {e}", "DOCKER_DOWN")

    # ═══════════════════════════════════════════════════════════════
    # US19 — Creer un conteneur dynamique
    # ═══════════════════════════════════════════════════════════════
    def create_container(self, reservation: Reservation, machine: Machine) -> str:
        """Cree et demarre un conteneur pour la réservation, retourne le container_id."""
        container_name = f"lab-reservation-{reservation.id}"
        # Verifier que l'image existe localement
        try:
            self.client.images.get(machine.image)
        except ImageNotFound:
            # Essayer de pull
            try:
                print(f"[container] pulling image {machine.image}...")
                self.client.images.pull(machine.image)
            except APIError as e:
                raise ContainerError(f"Image {machine.image} introuvable: {e}", "IMAGE_NOT_FOUND")
        # Config du conteneur
        try:
            container = self.client.containers.run(
                image=machine.image,
                name=container_name,
                detach=True,                              
                mem_limit=f"{reservation.ram_mb}m",       
                nano_cpus=int(reservation.cpu * 1e9),     
                network="bridge",                        
                labels={
                    # Traefik utilisera ces labels
                    "traefik.enable": "true",
                    "traefik.http.routers.lab-{}.rule".format(reservation.id):
                        f"Host(`lab-{reservation.id}.lab.local`)",
                    "traefik.http.services.lab-{}.loadbalancer.server.port".format(reservation.id):
                        str(machine.port),
                    # Metadonnees utiles
                    "lab.reservation_id": str(reservation.id),
                    "lab.user_id":        str(reservation.user_id),
                    "lab.machine":        machine.name,
                    "lab.expires_at":     reservation.end_time.isoformat(),
                },
                # Commande : garder le conteneur vivant
                command=["sleep", "infinity"],
                restart_policy={"Name": "unless-stopped"},
            )
            print(f"[container] created {container_name} (id={container.id[:12]})")
            return container.id

        except APIError as e:
            raise ContainerError(f"Échec docker run: {e}", "RUN_FAILED")

    # ═══════════════════════════════════════════════════════════════
    # US20 — Cycle de vie
    # ═══════════════════════════════════════════════════════════════
    def stop_container(self, container_id: str, timeout: int = 10) -> None:
        try:
            c = self.client.containers.get(container_id)
            c.stop(timeout=timeout)
            print(f"[container] stopped {container_id[:12]}")
        except docker.errors.NotFound:
            print(f"[container] {container_id[:12]} introuvable (déjà supprimé ?)")
        except APIError as e:
            raise ContainerError(f"Échec stop: {e}", "STOP_FAILED")

    def start_container(self, container_id: str) -> None:
        try:
            c = self.client.containers.get(container_id)
            c.start()
            print(f"[container] started {container_id[:12]}")
        except APIError as e:
            raise ContainerError(f"Échec start: {e}", "START_FAILED")

    def restart_container(self, container_id: str) -> None:
        try:
            c = self.client.containers.get(container_id)
            c.restart(timeout=10)
            print(f"[container] restarted {container_id[:12]}")
        except APIError as e:
            raise ContainerError(f"Échec restart: {e}", "RESTART_FAILED")

    def pause_container(self, container_id: str) -> None:
        try:
            c = self.client.containers.get(container_id)
            c.pause()
            print(f"[container] paused {container_id[:12]}")
        except APIError as e:
            raise ContainerError(f"Échec pause: {e}", "PAUSE_FAILED")

    def remove_container(self, container_id: str, force: bool = True) -> None:
        """suppression (avec nettoyage automatique)."""
        try:
            c = self.client.containers.get(container_id)
            c.remove(force=force, v=True)   
            print(f"[container] removed {container_id[:12]}")
        except docker.errors.NotFound:
            print(f"[container] {container_id[:12]} introuvable (déjà supprimé)")
        except APIError as e:
            raise ContainerError(f"Échec remove: {e}", "REMOVE_FAILED")

    # ═══════════════════════════════════════════════════════════════
    # US21 — Synchroniser Docker ↔ DB
    # ═══════════════════════════════════════════════════════════════
    def inspect_container(self, container_id: str) -> dict | None:
        """Retourne etat du conteneur"""
        try:
            c = self.client.containers.get(container_id)
            return {
                "id":     c.id,
                "status": c.status,       
                "image":  c.image.tags[0] if c.image.tags else "",
                "labels": c.labels,
            }
        except docker.errors.NotFound:
            return None
        except APIError as e:
            raise ContainerError(f"Échec inspect: {e}", "INSPECT_FAILED")

    def list_lab_containers(self) -> list[dict]:
        """Liste tous les conteneurs avec label lab.reservation_id."""
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": "lab.reservation_id"},
            )
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "reservation_id": c.labels.get("lab.reservation_id"),
                }
                for c in containers
            ]
        except APIError as e:
            raise ContainerError(f"Échec list: {e}", "LIST_FAILED")