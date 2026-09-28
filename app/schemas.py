from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models import MachineStatus, ReservationStatus, ResourceStatus, ResourceType, WorkerStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserOut(ORMModel):
    id: UUID
    email: EmailStr
    is_active: bool
    created_at: datetime


class Login(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ImageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    docker_image: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class ResourceCreate(BaseModel):
    resource_type: ResourceType
    total_capacity: int = Field(ge=0)


class ResourceOut(ORMModel):
    id: UUID
    worker_id: UUID
    resource_type: ResourceType
    total_capacity: int
    allocated_capacity: int
    status: ResourceStatus
    updated_at: datetime


class WorkerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(min_length=1, max_length=255)
    resources: list[ResourceCreate] = Field(min_length=1)


class WorkerOut(ORMModel):
    id: UUID
    name: str
    endpoint: str
    status: WorkerStatus
    last_heartbeat: datetime | None
    resources: list[ResourceOut]


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    image_id: UUID
    worker_id: UUID | None = None
    cpu: int = Field(gt=0)
    ram_mb: int = Field(gt=0)


class MachineOut(ORMModel):
    id: UUID
    name: str
    image_id: UUID
    worker_id: UUID | None
    container_id: str | None
    cpu: int
    ram_mb: int
    status: MachineStatus


class ReservationCreate(BaseModel):
    machine_id: UUID
    duration_minutes: int = Field(ge=5, le=1440)


class ReservationOut(ORMModel):
    id: UUID
    user_id: UUID
    machine_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: ReservationStatus
