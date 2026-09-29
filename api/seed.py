# Scripts seed data for dev
from app.database import SessionLocal
from app.models import User, Machine
from app.core.security import hash_password

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
               {"name": "kali", "image": "kalilinux/kali-rolling", "cpu_min": 1, "ram_min_mb": 512,  "port": 22},
               {"name": "ubuntu", "image": "ubuntu:22.04", "cpu_min": 1, "ram_min_mb": 512,  "port": 22},
               {"name": "alpine", "image": "alpine:3.19", "cpu_min": 1, "ram_min_mb": 256,  "port": 22},
          ]
          for m in machines:
               if not db.query(Machine).filter_by(name=m["name"]).first():
                    db.add(Machine(**m))
                    print(f"Created machine: {m['name']}")

          db.commit()
          print("\n Seed termine.")
     finally:
          db.close()

if __name__ == "__main__":
    main()