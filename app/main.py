from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Image, Machine, MachineStatus, Reservation, ReservationStatus, Resource, User, Worker, WorkerStatus
from app.schemas import (ImageCreate, Login, MachineCreate, MachineOut, ReservationCreate,
                         ReservationOut, ResourceCreate, ResourceOut, Token, UserCreate,
                         UserOut, WorkerCreate, WorkerOut)
from app.security import create_token, get_current_user, hash_password, verify_password

app = FastAPI(title="Ephemeral Machines API", version="0.1.0")


def commit(db: Session, entity):
    try:
        db.add(entity)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A resource with this unique value already exists")
    db.refresh(entity)
    return entity


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "ok"}


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    return commit(db, User(email=data.email, password_hash=hash_password(data.password)))


@app.post("/login", response_model=Token)
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_token(user))


@app.post("/logout", status_code=204)
def logout(_: User = Depends(get_current_user)):
    # JWT is stateless; the client must discard the token. A token deny-list can be added later.
    return Response(status_code=204)


@app.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.post("/images", status_code=201)
def create_image(data: ImageCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return commit(db, Image(**data.model_dump()))


@app.get("/machines", response_model=list[MachineOut])
def list_machines(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Machine).filter(Machine.status != MachineStatus.DELETED).all()


@app.get("/machines/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    machine = db.get(Machine, machine_id)
    if not machine or machine.status == MachineStatus.DELETED:
        raise HTTPException(404, "Machine not found")
    return machine


@app.post("/machines", response_model=MachineOut, status_code=201)
def create_machine(data: MachineCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.get(Image, data.image_id):
        raise HTTPException(404, "Image not found")
    if data.worker_id and not db.get(Worker, data.worker_id):
        raise HTTPException(404, "Worker not found")
    return commit(db, Machine(**data.model_dump()))


@app.delete("/machines/{machine_id}", status_code=204)
def delete_machine(machine_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    machine = db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(404, "Machine not found")
    machine.status = MachineStatus.DELETED
    db.commit()
    return Response(status_code=204)


def set_machine_status(machine_id: UUID, target: MachineStatus, db: Session):
    machine = db.get(Machine, machine_id)
    if not machine or machine.status == MachineStatus.DELETED:
        raise HTTPException(404, "Machine not found")
    machine.status = target
    db.commit(); db.refresh(machine)
    return machine


@app.post("/machines/{machine_id}/start", response_model=MachineOut)
def start_machine(machine_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return set_machine_status(machine_id, MachineStatus.RUNNING, db)


@app.post("/machines/{machine_id}/stop", response_model=MachineOut)
def stop_machine(machine_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return set_machine_status(machine_id, MachineStatus.STOPPED, db)


@app.get("/reservations", response_model=list[ReservationOut])
def list_reservations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Reservation).filter(Reservation.user_id == user.id).order_by(Reservation.created_at.desc()).all()


@app.post("/reservations", response_model=ReservationOut, status_code=201)
def reserve(data: ReservationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    machine = db.get(Machine, data.machine_id)
    if not machine or machine.status not in (MachineStatus.PENDING, MachineStatus.STOPPED):
        raise HTTPException(409, "Machine is unavailable")
    active = db.query(Reservation).filter(Reservation.machine_id == machine.id, Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.ACTIVE])).first()
    if active:
        raise HTTPException(409, "Machine already has an active reservation")
    now = datetime.now(timezone.utc)
    reservation = Reservation(user_id=user.id, machine_id=machine.id, starts_at=now, ends_at=now + timedelta(minutes=data.duration_minutes), status=ReservationStatus.ACTIVE)
    machine.status = MachineStatus.RUNNING
    db.add(reservation)
    return commit(db, reservation)


@app.get("/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(404, "Reservation not found")
    return reservation


@app.delete("/reservations/{reservation_id}", status_code=204)
def release(reservation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(404, "Reservation not found")
    if reservation.status in (ReservationStatus.RELEASED, ReservationStatus.EXPIRED):
        raise HTTPException(409, "Reservation is already closed")
    reservation.status = ReservationStatus.RELEASED
    machine = db.get(Machine, reservation.machine_id)
    if machine: machine.status = MachineStatus.STOPPED
    db.commit()
    return Response(status_code=204)


@app.get("/workers", response_model=list[WorkerOut])
def list_workers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Worker).all()


@app.get("/resources", response_model=list[ResourceOut])
def list_resources(worker_id: UUID | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Resource)
    if worker_id:
        query = query.filter(Resource.worker_id == worker_id)
    return query.all()


@app.post("/workers/{worker_id}/resources", response_model=ResourceOut, status_code=201)
def create_resource(worker_id: UUID, data: ResourceCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.get(Worker, worker_id):
        raise HTTPException(404, "Worker not found")
    return commit(db, Resource(worker_id=worker_id, **data.model_dump()))


@app.post("/workers/register", response_model=WorkerOut, status_code=201)
def register_worker(data: WorkerCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    worker_data = data.model_dump(exclude={"resources"})
    worker = Worker(**worker_data, last_heartbeat=datetime.now(timezone.utc))
    worker.resources = [Resource(**resource.model_dump()) for resource in data.resources]
    try:
        db.add(worker)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Worker name, endpoint, or resource type already exists")
    db.refresh(worker)
    return worker


@app.post("/workers/{worker_id}/heartbeat", response_model=WorkerOut)
def heartbeat(worker_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    worker = db.get(Worker, worker_id)
    if not worker: raise HTTPException(404, "Worker not found")
    worker.last_heartbeat = datetime.now(timezone.utc)
    worker.status = WorkerStatus.AVAILABLE
    db.commit(); db.refresh(worker)
    return worker


@app.get("/workers/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    worker = db.get(Worker, worker_id)
    if not worker: raise HTTPException(404, "Worker not found")
    return worker
