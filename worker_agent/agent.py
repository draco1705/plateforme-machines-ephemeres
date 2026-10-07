import psutil
import requests
import time
import socket
import os

API_URL = os.getenv("CONTROLLER_API_URL", "http://192.168.56.10:8000")
WORKER_ID = socket.gethostname()

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def register_worker():
    payload = {
        "name": WORKER_ID,
        "ip": get_ip(),
        "cpu_total": psutil.cpu_count(),
        "ram_total_mb": int(psutil.virtual_memory().total / (1024 * 1024))
    }
    while True:
        try:
            print(f"Registering worker {WORKER_ID} at {API_URL}...")
            resp = requests.post(f"{API_URL}/workers/register", json=payload)
            if resp.status_code == 201:
                print("Registered successfully.")
                break
        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to Controller API: {e}")
        time.sleep(5)

def send_heartbeat():
    while True:
        try:
            payload = {
                "name": WORKER_ID,
                "cpu_used": 0,
                "ram_used_mb": 0
            }
            resp = requests.post(f"{API_URL}/workers/heartbeat", json=payload)
            if resp.status_code != 204:
                print(f"Heartbeat failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Error sending heartbeat: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    register_worker()
    send_heartbeat()
