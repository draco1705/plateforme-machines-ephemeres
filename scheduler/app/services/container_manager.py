from pathlib import Path

import docker
import httpx
from app.models.machine import Machine
from app.models.reservation import Reservation
from app.models.worker import Worker
from docker.errors import APIError, DockerException, ImageNotFound

TRAEFIK_DYNAMIC_DIR = Path("/opt/labhacker/traefik-dynamic")


class ContainerError(Exception):
    """Erreur de gestion de conteneur."""
    def __init__(self, message: str, code: str = "CONTAINER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ContainerManager:
    """Gère les conteneurs en déléguant au Worker Agent via HTTP, avec fallback local."""
    CREATE_TIMEOUT = 120   
    REMOVE_TIMEOUT = 30
    STATUS_TIMEOUT = 10
    HEALTH_TIMEOUT = 5

    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException:
            self.client = None

    @staticmethod        
    def _worker_url(worker: Worker) -> str:
        port = getattr(worker, "port", 8001) or 8001
        ip = getattr(worker, "ip", "127.0.0.1")
        return f"http://{ip}:{port}"

    def _create_container_locally(self, reservation: Reservation, machine: Machine) -> dict[str, any]:
        """Fallback local si le worker agent n'est pas joignable mais Docker est disponible."""
        if self.client is None:
            raise ContainerError("Docker local indisponible et Worker injoignable", "DOCKER_DOWN")

        container_name = f"lab-reservation-{reservation.id}"
        try:
            self.client.images.get(machine.image)
        except ImageNotFound:
            try:
                print(f"[container] Pulling image {machine.image} localement...")
                self.client.images.pull(machine.image)
            except APIError as e:
                raise ContainerError(f"Image {machine.image} introuvable: {e}", "IMAGE_NOT_FOUND")

        labels = {
            "traefik.enable": "true",
            "traefik.docker.network": "lab-net",
            f"traefik.http.routers.lab-{reservation.id}.rule": f"Host(`lab-{reservation.id}.lab.local`)",
            f"traefik.http.routers.lab-{reservation.id}.entrypoints": "websecure",
            f"traefik.http.routers.lab-{reservation.id}.tls": "true",
            f"traefik.http.services.lab-{reservation.id}.loadbalancer.server.port": str(getattr(machine, "port", 80) or 80),
            "lab.reservation_id": str(reservation.id),
            "lab.user_id": str(reservation.user_id),
            "lab.machine": machine.name,
            "lab.expires_at": reservation.end_time.isoformat() if reservation.end_time else "",
        }

        cmd = None
        if "alpine" in machine.image:
            cmd = ["sh", "-c", f"while true; do (echo -e 'HTTP/1.1 200 OK\\r\\nContent-Type: text/html\\r\\n\\r\\nHello from lab-{reservation.id} on alpine') | nc -l -p 80; done"]

        try:
            container = self.client.containers.run(
                image=machine.image,
                name=container_name,
                detach=True,
                mem_limit=f"{reservation.ram_mb}m",
                nano_cpus=int(reservation.cpu * 1e9),
                network="lab-net",
                labels=labels,
                command=cmd,
                restart_policy={"Name": "unless-stopped"},
            )
            print(f"[container] local created {container_name} (id={container.id[:12]})")
            return {
                "container_id": container.id,
                "container_name": container_name,
                "worker_name": "local",
                "worker_ip": "127.0.0.1",
                "host_port": 80,
            }
        except APIError as e:
            raise ContainerError(f"Échec docker run: {e}", "RUN_FAILED")

    # ═══════════════════════════════════════════════════════════════
    # US19 — Creer un conteneur dynamique
    # ═══════════════════════════════════════════════════════════════
    def create_container(self, worker: Worker | None, reservation: Reservation, machine: Machine) -> dict[str, any]:
        if worker and worker.ip and worker.ip != "127.0.0.1":
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
                    message = detail.get("message", r.text) if isinstance(detail, dict) else str(detail)
                    code = detail.get("code", "CREATE_FAILED") if isinstance(detail, dict) else "CREATE_FAILED"
                except Exception:
                    message = r.text
                    code = "CREATE_FAILED"
                raise ContainerError(f"Worker {worker.name} : HTTP {r.status_code} — {message}", code)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
                print(f"[scheduler] Worker {worker.name} injoignable ({e}), tentative fallback local...")
                if self.client:
                    return self._create_container_locally(reservation, machine)
                raise ContainerError(f"Worker {worker.name} injoignable ({e}) et Docker local indisponible", "WORKER_UNREACHABLE")

        # Fallback local
        return self._create_container_locally(reservation, machine)

    # ═══════════════════════════════════════════════════════════════
    # US20 — Cycle de vie
    # ═══════════════════════════════════════════════════════════════
    def stop_container(self, container_id: str, timeout: int = 10) -> None:
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                c.stop(timeout=timeout)
                print(f"[container] stopped {container_id[:12]}")
            except docker.errors.NotFound:
                pass
            except APIError as e:
                raise ContainerError(f"Échec stop: {e}", "STOP_FAILED")

    def start_container(self, container_id: str) -> None:
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                c.start()
                print(f"[container] started {container_id[:12]}")
            except APIError as e:
                raise ContainerError(f"Échec start: {e}", "START_FAILED")

    def restart_container(self, container_id: str) -> None:
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                c.restart(timeout=10)
                print(f"[container] restarted {container_id[:12]}")
            except APIError as e:
                raise ContainerError(f"Échec restart: {e}", "RESTART_FAILED")

    def pause_container(self, container_id: str) -> None:
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                c.pause()
                print(f"[container] paused {container_id[:12]}")
            except APIError as e:
                raise ContainerError(f"Échec pause: {e}", "PAUSE_FAILED")

    def remove_container(self, worker: Worker | None, container_id: str, force: bool = True) -> None:
        if worker and worker.ip and worker.ip != "127.0.0.1":
            url = f"{self._worker_url(worker)}/containers/{container_id}"
            params = {"force": force}
            try:
                r = httpx.delete(url, params=params, timeout=self.REMOVE_TIMEOUT)
                if r.status_code in (204, 404):
                    print(f"[scheduler] Worker {worker.name} : container {container_id[:12]} removed")
                    return
            except httpx.HTTPError as e:
                print(f"[scheduler] Worker {worker.name} injoignable pour delete ({e}), tentative locale...")

        # Fallback local
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                c.remove(force=force, v=True)
                print(f"[container] removed locally {container_id[:12]}")
            except docker.errors.NotFound:
                print(f"[container] {container_id[:12]} introuvable (déjà supprimé)")
            except APIError as e:
                raise ContainerError(f"Échec remove: {e}", "REMOVE_FAILED")

    def get_container_status(self, worker: Worker | None, container_id: str) -> str | None:
        if worker and worker.ip and worker.ip != "127.0.0.1":
            url = f"{self._worker_url(worker)}/containers/{container_id}/status"
            try:
                r = httpx.get(url, timeout=self.STATUS_TIMEOUT)
                if r.status_code == 200:
                    return r.json().get("status")
            except httpx.HTTPError:
                pass
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                return c.status
            except Exception:
                pass
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
        if self.client:
            try:
                c = self.client.containers.get(container_id)
                return {
                    "id": c.id,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "",
                    "labels": c.labels,
                }
            except docker.errors.NotFound:
                return None
            except APIError as e:
                raise ContainerError(f"Échec inspect: {e}", "INSPECT_FAILED")
        return None

    def list_lab_containers(self) -> list[dict]:
        """Liste tous les conteneurs avec label lab.reservation_id."""
        if self.client:
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
        return []