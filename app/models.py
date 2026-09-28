import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class WorkerStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class MachineStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class ResourceType(str, enum.Enum):
    CPU = "CPU"
    RAM_MB = "RAM_MB"
    CONTAINER_SLOT = "CONTAINER_SLOT"
    PORT = "PORT"


class ResourceStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")


class Image(Base):
    __tablename__ = "images"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    docker_image: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[WorkerStatus] = mapped_column(Enum(WorkerStatus), default=WorkerStatus.AVAILABLE, index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    machines: Mapped[list["Machine"]] = relationship(back_populates="worker")
    resources: Mapped[list["Resource"]] = relationship(back_populates="worker", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("worker_id", "resource_type", name="uq_resource_worker_type"),
        CheckConstraint("total_capacity >= 0", name="ck_resource_total_non_negative"),
        CheckConstraint("allocated_capacity >= 0", name="ck_resource_allocated_non_negative"),
        CheckConstraint("allocated_capacity <= total_capacity", name="ck_resource_allocated_within_total"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id"), index=True)
    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType), index=True)
    total_capacity: Mapped[int] = mapped_column(Integer)
    allocated_capacity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ResourceStatus] = mapped_column(Enum(ResourceStatus), default=ResourceStatus.AVAILABLE, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    worker: Mapped[Worker] = relationship(back_populates="resources")


class Machine(Base):
    __tablename__ = "machines"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id"))
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id"), nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    cpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    status: Mapped[MachineStatus] = mapped_column(Enum(MachineStatus), default=MachineStatus.PENDING, index=True)
    worker: Mapped[Worker | None] = relationship(back_populates="machines")


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machines.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus), default=ReservationStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="reservations")
