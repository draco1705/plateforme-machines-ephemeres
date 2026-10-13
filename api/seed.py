# Scripts seed data for dev
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import Machine, User, Worker


def main():
     db = SessionLocal()
     try:
          #Admin user
          if not db.query(User).filter_by(email="admin@lab.local").first():
               admin = User(
                    email="admin@lab.local",
                    password_hash = hash_password("admin12345"),
                    role = "admin",
               )
               db.add(admin)
               print("Create admin: admin@lab.local / admin12345")
          
          # Normal User
          if not db.query(User).filter_by(email="user@lab.local").first():
               user = User(
                    email = "user@lab.local",
                    password_hash = hash_password("user12345"),
                    role = "user",
               )
               db.add(user)
               print("Create user: user@lab.local / user12345")
          
          # Machine
          machines = [
               {"name": "kali",   "image": "kalilinux/kali-rolling", "cpu_min": 1, "ram_min_mb": 512, "port": 80},
               {"name": "nginx",  "image": "nginxdemos/hello",       "cpu_min": 1, "ram_min_mb": 256, "port": 80},
               {"name": "python", "image": "python:3.12-alpine",     "cpu_min": 1, "ram_min_mb": 256, "port": 8000},
               {"name": "alpine", "image": "alpine:3.19",            "cpu_min": 1, "ram_min_mb": 256, "port": 80},
          ]

          for m in machines:
               if not db.query(Machine).filter_by(name=m["name"]).first():
                    db.add(Machine(**m))
                    print(f"Created machine: {m['name']}")

          # Workers cluster
          workers = [
               {"name": "worker1", "ip": "192.168.56.11", "port": 8001, "cpu_total": 1, "ram_total_mb": 957, "max_containers": 4},
               {"name": "worker2", "ip": "192.168.56.12", "port": 8001, "cpu_total": 1, "ram_total_mb": 957, "max_containers": 4},
               {"name": "worker3", "ip": "192.168.56.13", "port": 8001, "cpu_total": 1, "ram_total_mb": 957, "max_containers": 4},
          ]
          for w in workers:
               if not db.query(Worker).filter_by(name=w["name"]).first():
                    db.add(Worker(**w))
                    print(f"Created worker: {w['name']} ({w['ip']})")

          db.commit()
          print("\n Seed termine.")
     finally:
          db.close()

if __name__ == "__main__":
    main()