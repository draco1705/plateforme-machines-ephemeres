import signal
import time

from app.config import settings
from app.jobs.auto_heal import check_and_auto_heal
from app.jobs.cancel_running import cancel_running
from app.jobs.expire_pending import expire_pending_timeout
from app.jobs.expire_running import expire_running
from app.jobs.process_pending import process_pending

_shutdown = False

def _handle_signal(signum, frame):
     global _shutdown
     print(f"\n[scheduler] signal {signum} recu - arret en cours...")
     _shutdown = True
def run_loop():
     print("=" * 60)
     print("[scheduler] démarrage")
     print(f"[scheduler] interval = {settings.SCHEDULER_INTERVAL_SECONDS}s")
     print(f"[scheduler] batch    = {settings.BATCH_SIZE}")
     print(f"[scheduler] DB       = {settings.DATABASE_URL}")
     print("=" * 60)
     signal.signal(signal.SIGINT, _handle_signal)
     signal.signal(signal.SIGTERM, _handle_signal)
     tick = 0
     while not _shutdown:
          tick += 1
          try:
               n_run = process_pending(settings.BATCH_SIZE)
               n_exp = expire_running(settings.BATCH_SIZE * 2)
               n_can = cancel_running(settings.BATCH_SIZE * 2)
               n_stuck = expire_pending_timeout()
               n_heal = check_and_auto_heal(settings.BATCH_SIZE)
               if n_run or n_exp or n_heal:
                    print(f"[scheduler] cycle #{tick}: {n_run} démarrées, {n_exp} expirées, {n_heal} réparées")
          except Exception as e:
               print(f"[scheduler] ERREUR cycle #{tick}: {e}")
          # Sommeil interruptible 
          for _ in range(settings.SCHEDULER_INTERVAL_SECONDS * 10):
               if _shutdown:
                    break
               time.sleep(0.1)
     print("[scheduler] arrêté proprement.")
     
if __name__ == "__main__":
    run_loop()