import docker
from docker.errors import DockerException, ImageNotFound, APIError
import os
from pathlib import Path
import httpx
from app.models.reservation import Reservation
from app.models.machine import Machine
from app.models.worker import Worker

TRAEFIK_DYNAMIC_DIR = Path("/opt/labhacker/traefik-dynamic")

class ContainerError(Exception):
    """Erreur de gestion de conteneur."""
    def __init__(self, message: str, code: str = "CONTAINER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ContainerManager:
    """Gère les conteneurs en déléguant au Worker Agent via HTTP."""
    # Timeouts HTTP
    CREATE_TIMEOUT = 120   
    REMOVE_TIMEOUT = 30
    STATUS_TIMEOUT = 10
    HEALTH_TIMEOUT = 5
    
    @staticmethod        
    def _worker_url(worker: Worker) -> str:
        port = getattr(worker, "port", 8001) or 8001
        ip = getattr(worker, "ip", "127.0.0.1")
        return f"http://{ip}:{port}"

    # ═══════════════════════════════════════════════════════════════
    # US19 — Creer un conteneur dynamique
    # ═══════════════════════════════════════════════════════════════
    def create_container(self, worker: Worker,reservation: Reservation, machine: Machine) -> dict[str, any]:
        payload = {
            "reservation_id": reservation.id,
            "image": machine.image,
            "cpu": reservation.cpu,
            "ram_mb": reservation.ram_mb,
            "port": getattr(machine, "port", 80) or 80,
            "expires_at": reservation.end_time.isoformat() if reservation.end_time else "",
        }
        url = f"{self._worker_url(worker)}/containers"

        try:
            r = httpx.post(url, json=payload, timeout=self.CREATE_TIMEOUT)
        except httpx.ConnectError:
            raise ContainerError(
                f"Worker {worker.name} injoignable ({worker.ip})",
                "WORKER_UNREACHABLE",
            )
        except httpx.TimeoutException:
            raise ContainerError(
                f"Worker {worker.name} timeout sau {self.CREATE_TIMEOUT}s",
                "WORKER_TIMEOUT",
            )
        except httpx.HTTPError as e:
            raise ContainerError(
                f"Erreur HTTP vers Worker {worker.name}: {e}",
                "WORKER_HTTP_ERROR",
            )

        if r.status_code == 201:
            data = r.json()
            container_id = data.get("container_id", "")
            print(
                f"[scheduler] Worker {worker.name} -> container "
                f"{container_id[:12]} (url=https://lab-{reservation.id}.lab.local)"
            )
            return data

        try:
            body = r.json()
            detail = body.get("detail", {}) if isinstance(body, dict) else r.text
            if isinstance(detail, dict):
                message = detail.get("message", r.text)
                code = detail.get("code", "CREATE_FAILED")
            else:
                message = str(detail)
                code = "CREATE_FAILED"
        except Exception:
            message = r.text
            code = "CREATE_FAILED"

        raise ContainerError(
            f"Worker {worker.name} : HTTP {r.status_code} — {message}",
            code,
        )

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

    def remove_container(self, worker: Worker, container_id: str,force: bool = True) -> None:
        url = f"{self._worker_url(worker)}/containers/{container_id}"
        params = {"force": force}
        try:
            r = httpx.delete(url, params=params, timeout=self.REMOVE_TIMEOUT)
        except httpx.HTTPError as e:
            raise ContainerError(f"Worker {worker.name} injoignable: {e}","WORKER_UNREACHABLE")

        if r.status_code in (204, 404):
            print(f"[scheduler] Worker {worker.name} : container {container_id[:12]} removed")
            return

        raise ContainerError(
            f"Worker {worker.name} : HTTP {r.status_code} — {r.text}",
            "REMOVE_FAILED",
        )

    def get_container_status(self, worker: Worker, container_id: str) -> str:
        url = f"{self._worker_url(worker)}/containers/{container_id}/status"
        try:
            r = httpx.get(url, timeout=self.STATUS_TIMEOUT)
            if r.status_code == 200:
                return r.json().get("status")
        except httpx.HTTPError:
            return None
        return None

    def ping_worker(self, worker: Worker) -> bool:
        url = f"{self._worker_url(worker)}/health"
        try:
            r = httpx.get(url, timeout=self.HEALTH_TIMEOUT)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

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