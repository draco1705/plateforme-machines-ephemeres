import docker
from app.models.machine import Machine
from app.models.reservation import Reservation
from docker.errors import APIError, DockerException, ImageNotFound


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
        # commande HTTP server pour que Traefik puisse router python http.server écoute sur port 80
        # if "alpine" in machine.image:
        #     # Alpine : python3 + nc fallback
        #     cmd = ["sh", "-c", f"while true; do echo \"Hello from lab-{reservation.id} on alpine\" | nc -l -p 80; done"]
        # else:
            # cmd = ["sh", "-c",
            #     f"python3 -m http.server 80 2>/dev/null || "
            #     f"(echo 'Hello from lab-{reservation.id}' > /tmp/index.html && "
            #     f"while true; do (echo -e 'HTTP/1.1 200 OK\\r\\nContent-Type: text/html\\r\\n\\r\\n'; "
            #     f"cat /tmp/index.html) | nc -l -p 80 -q 1; done)"]

        if "nginx" in machine.image:
            cmd = None  # Giữ nguyên entrypoint mặc định của Nginx để tự phục vụ port 80
        elif "alpine" in machine.image:
            cmd = [
                "sh", "-c",
                f"while true; do (echo -e 'HTTP/1.1 200 OK\\r\\nContent-Type: text/html\\r\\n\\r\\nHello from lab-{reservation.id} on alpine') | nc -l -p 80; done"
            ]
        else:
            cmd = [
                "sh", "-c",
                f"if command -v python3 >/dev/null 2>&1; then "
                f"python3 -m http.server 80; "
                f"else "
                f"while true; do (echo -e 'HTTP/1.1 200 OK\\r\\nContent-Type: text/html\\r\\n\\r\\nHello from lab-{reservation.id}') | nc -l -p 80; done; "
                f"fi"
            ]

        labels = {
            # Activer Traefik
            "traefik.enable": "true",
            "traefik.docker.network": "lab-net",

            # Router pour cette reservation
            f"traefik.http.routers.lab-{reservation.id}.rule":
                f"Host(`lab-{reservation.id}.lab.local`)",
            f"traefik.http.routers.lab-{reservation.id}.entrypoints":
                "websecure",
            f"traefik.http.routers.lab-{reservation.id}.tls": "true",
            f"traefik.http.routers.lab-{reservation.id}.middlewares":
                "security-headers@file",

            # Service pour cette reservation
            f"traefik.http.services.lab-{reservation.id}.loadbalancer.server.port":
                "80",

            # Metadonnées
            "lab.reservation_id": str(reservation.id),
            "lab.user_id":        str(reservation.user_id),
            "lab.machine":        machine.name,
            "lab.expires_at":     reservation.end_time.isoformat(),
        }
        # Config du conteneur
        try:
            container = self.client.containers.run(
                image=machine.image,
                name=container_name,
                detach=True,                              
                mem_limit=f"{reservation.ram_mb}m",       
                nano_cpus=int(reservation.cpu * 1e9),     
                network="lab-net",                        
                labels=labels,
                # Commande : garder le conteneur vivant
                command=cmd,
                restart_policy={"Name": "unless-stopped"},
            )
            print(f"[container] created {container_name} (id={container.id[:12]}) url=https://lab-{reservation.id}.lab.local")
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