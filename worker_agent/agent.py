# import psutil
# import requests
# import time
# import socket
# import os

# API_URL = os.getenv("CONTROLLER_API_URL", "http://192.168.56.10:8000")
# WORKER_ID = socket.gethostname()

# def get_ip():
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     try:
#         s.connect(('10.255.255.255', 1))
#         IP = s.getsockname()[0]
#     except Exception:
#         IP = '127.0.0.1'
#     finally:
#         s.close()
#     return IP

# def register_worker():
#     payload = {
#         "id": WORKER_ID,
#         "ip": get_ip(),
#         "cpu": psutil.cpu_count(),
#         "ram": psutil.virtual_memory().total
#     }
#     while True:
#         try:
#             print(f"Registering worker {WORKER_ID} at {API_URL}...")
#             resp = requests.post(f"{API_URL}/workers/register", json=payload)
#             if resp.status_code == 201:
#                 print("Registered successfully.")
#                 break
#         except requests.exceptions.RequestException as e:
#             print(f"Failed to connect to Controller API: {e}")
#         time.sleep(5)

# def send_heartbeat():
#     while True:
#         stats = {
#             "cpu_percent": psutil.cpu_percent(),
#             "ram_percent": psutil.virtual_memory().percent
#         }
#         try:
#             resp = requests.post(f"{API_URL}/workers/heartbeat", json={"id": WORKER_ID, "stats": stats})
#             if resp.status_code != 200:
#                 print(f"Heartbeat failed: {resp.status_code} - {resp.text}")
#         except Exception as e:
#             print(f"Error sending heartbeat: {e}")
        
#         time.sleep(5)

# if __name__ == "__main__":
#     register_worker()
#     send_heartbeat()


import psutil
import requests
import time
import socket
import threading
import os
from datetime import datetime
import docker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from docker.errors import DockerException, ImageNotFound, APIError

API_URL = os.getenv("CONTROLLER_API_URL", "http://192.168.56.10:8000")
WORKER_NAME = os.getenv("WORKER_NAME", socket.gethostname())
WORKER_PORT = int(os.getenv("WORKER_PORT", "8001"))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "5"))
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "lab-net")
MAX_CONTAINERS = int(os.getenv("MAX_CONTAINERS", "4"))

def get_ip() -> str:
    """IP sur le réseau privé (utilise controller comme route)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Utilise l'IP du controller (dans le même subnet)
        host = API_URL.split("//")[-1].split(":")[0]
        s.connect((host, 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


WORKER_IP = get_ip()
CPU_TOTAL = psutil.cpu_count(logical=True)
RAM_TOTAL_MB = psutil.virtual_memory().total // (1024 * 1024)

# ────────────────────────────────────────────────────────────
# DOCKER CLIENT
# ────────────────────────────────────────────────────────────
try:
    docker_client = docker.from_env()
    docker_client.ping()
    print("[agent] Docker OK")
except DockerException as e:
    print(f"[agent] Docker indisponible: {e}")
    docker_client = None


def get_container_usage() -> dict:
    """CPU/RAM utilisés par les conteneurs lab."""
    if docker_client is None:
        return {"cpu_used": 0, "ram_used_mb": 0, "container_count": 0}
    try:
        containers = docker_client.containers.list(filters={"label": "lab.reservation_id"})
        cpu_used = 0
        ram_used = 0
        for c in containers:
            hc = c.attrs.get("HostConfig", {})
            cpu_used += int(hc.get("NanoCpus", 0) / 1e9)
            ram_used += int(hc.get("Memory", 0) / (1024 * 1024))
        return {
            "cpu_used": cpu_used,
            "ram_used_mb": ram_used,
            "container_count": len(containers),
        }
    except Exception:
        return {"cpu_used": 0, "ram_used_mb": 0, "container_count": 0}


# ────────────────────────────────────────────────────────────
# FASTAPI APP pour recevoir des demandes de Scheduler
# ────────────────────────────────────────────────────────────
app = FastAPI(title=f"Worker Agent — {WORKER_NAME}")

class ContainerCreateRequest(BaseModel):
    reservation_id: int
    image: str
    cpu: int = Field(ge=1, le=8)
    ram_mb: int = Field(ge=256)
    port: int = 80
    expires_at: str = ""


@app.get("/")
def root():
    return {"worker": WORKER_NAME, "ip": WORKER_IP, "port": WORKER_PORT}

@app.get("/health")
def health():
    docker_ok = docker_client is not None
    try:
        if docker_client:
            docker_client.ping()
    except Exception:
        docker_ok = False
    return {
        "status": "ok" if docker_ok else "degraded",
        "worker": WORKER_NAME,
        "docker": "ok" if docker_ok else "down",
    }


@app.get("/status")
def status():
    usage = get_container_usage()
    return {
        "name": WORKER_NAME,
        "ip": WORKER_IP,
        "port": WORKER_PORT,
        "cpu_total": CPU_TOTAL,
        "cpu_used": usage["cpu_used"],
        "ram_total_mb": RAM_TOTAL_MB,
        "ram_used_mb": usage["ram_used_mb"],
        "container_count": usage["container_count"],
        "max_containers": MAX_CONTAINERS,
    }


@app.post("/containers", status_code=201)
def create_container(req: ContainerCreateRequest):
    """Scheduler appelle pour créer un conteneur."""
    if docker_client is None:
        raise HTTPException(500, {"code": "DOCKER_DOWN", "message": "Docker indisponible"})

    container_name = f"lab-reservation-{req.reservation_id}"

    # Vérifier image
    try:
        docker_client.images.get(req.image)
    except ImageNotFound:
        try:
            print(f"[agent] Pulling {req.image}...")
            docker_client.images.pull(req.image)
        except APIError as e:
            raise HTTPException(500, {"code": "IMAGE_NOT_FOUND", "message": str(e)})

    # Labels Traefik
    labels = {
        "traefik.enable": "true",
        "traefik.docker.network": DOCKER_NETWORK,
        f"traefik.http.routers.lab-{req.reservation_id}.rule":
            f"Host(`lab-{req.reservation_id}.lab.local`)",
        f"traefik.http.routers.lab-{req.reservation_id}.entrypoints": "websecure",
        f"traefik.http.routers.lab-{req.reservation_id}.tls": "true",
        f"traefik.http.services.lab-{req.reservation_id}.loadbalancer.server.port": str(req.port),
        "lab.reservation_id": str(req.reservation_id),
        "lab.expires_at": req.expires_at,
    }

    try:
        container = docker_client.containers.run(
            image=req.image,
            name=container_name,
            detach=True,
            mem_limit=f"{req.ram_mb}m",
            nano_cpus=int(req.cpu * 1e9),
            network=DOCKER_NETWORK,
            labels=labels,
            ports={"22/tcp": None},
            restart_policy={"Name": "unless-stopped"},
        )

        container.reload()
        ports = container.attrs["NetworkSettings"]["Ports"]
        host_port = None
        if ports and "80/tcp" in ports:
            host_port = int(ports["80/tcp"][0]["HostPort"])

        print(f"[agent] Created {container_name} (id={container.id[:12]})")
        
        return {
            "container_id": container.id,
            "container_name": container_name,
            "worker_name": WORKER_NAME,
            "worker_ip": WORKER_IP,
            "host_port": host_port,
        }
    except APIError as e:
        raise HTTPException(500, {"code": "RUN_FAILED", "message": str(e)})


@app.delete("/containers/{container_id}", status_code=204)
def delete_container(container_id: str):
    """Scheduler appelle pour détruire un conteneur."""
    if docker_client is None:
        raise HTTPException(500, "Docker indisponible")
    try:
        c = docker_client.containers.get(container_id)
        c.remove(force=True, v=True)
        print(f"[agent] Removed {container_id[:12]}")
    except docker.errors.NotFound:
        print(f"[agent] {container_id[:12]} déjà supprimé")
    except APIError as e:
        raise HTTPException(500, str(e))


# ────────────────────────────────────────────────────────────
# HEARTBEAT — Register + périodique
# ────────────────────────────────────────────────────────────
def register_worker() -> bool:
    payload = {
        "name": WORKER_NAME,
        "ip": WORKER_IP,
        "port": WORKER_PORT,
        "cpu_total": CPU_TOTAL,
        "ram_total_mb": RAM_TOTAL_MB,
        "max_containers": MAX_CONTAINERS,
    }
    try:
        print(f"[agent] Registering {WORKER_NAME} at {API_URL}...")
        r = requests.post(f"{API_URL}/workers/register", json=payload, timeout=10)
        if r.status_code in (200, 201):
            print(f"[agent] Registered OK ({r.status_code})")
            return True
        print(f"[agent] Register failed: {r.status_code} {r.text}")
    except requests.RequestException as e:
        print(f"[agent] Controller unreachable: {e}")
    return False


def send_heartbeat() -> None:
    usage = get_container_usage()
    payload = {
        "name": WORKER_NAME,
        "cpu_used": usage["cpu_used"],
        "ram_used_mb": usage["ram_used_mb"],
    }
    try:
        r = requests.post(f"{API_URL}/workers/heartbeat", json=payload, timeout=5)
        if r.status_code == 204:
            print(f"[agent] Heartbeat OK — cpu={usage['cpu_used']}, ram={usage['ram_used_mb']}MB")
        else:
            print(f"[agent] Heartbeat failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[agent] Heartbeat error: {e}")


def heartbeat_loop():
    # Register avec retry
    while not register_worker():
        time.sleep(5)

    # Boucle heartbeat
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        send_heartbeat()


# ────────────────────────────────────────────────────────────
# ENTRYPOINT
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print(f"[agent] Starting worker agent")
    print(f"[agent]   Name    : {WORKER_NAME}")
    print(f"[agent]   IP      : {WORKER_IP}")
    print(f"[agent]   Port    : {WORKER_PORT}")
    print(f"[agent]   CPU     : {CPU_TOTAL}")
    print(f"[agent]   RAM     : {RAM_TOTAL_MB} MB")
    print(f"[agent]   Controller: {API_URL}")

    # Démarrer le thread heartbeat en arrière-plan
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()

    # Démarrer le serveur HTTP (bloquant)
    uvicorn.run(app, host="0.0.0.0", port=WORKER_PORT, log_level="info")