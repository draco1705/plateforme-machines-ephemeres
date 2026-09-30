import time
import requests
import os

API_URL = os.getenv("LABHACKER_API_URL", "http://localhost:8000")
HEARTBEAT_TIMEOUT = 15 # seconds

def check_workers():
    try:
        resp = requests.get(f"{API_URL}/workers")
        if resp.status_code == 200:
            workers = resp.json()
            current_time = time.time()
            for w in workers:
                last_hb = w.get("last_heartbeat", 0)
                if current_time - last_hb > HEARTBEAT_TIMEOUT and w["status"] != "OFFLINE":
                    print(f"ALERT: Worker {w['id']} has gone offline! Last heartbeat: {current_time - last_hb:.1f}s ago")
                    trigger_rescheduling(w['id'])
    except Exception as e:
        print(f"Error checking workers: {e}")

def trigger_rescheduling(worker_id):
    print(f"Triggering rescheduling for containers on {worker_id}...")
    pass

if __name__ == "__main__":
    print("Starting Monitoring & Auto-repair Service...")
    while True:
        check_workers()
        time.sleep(5)
