# app/main.py
from fastapi import FastAPI
from app.config import settings
from app.database import Base, engine
from app.routers import users, machines, reservations, workers, health
from app.exceptions import register_exception_handlers


app = FastAPI(title=settings.APP_Name, version="0.1.0")
register_exception_handlers(app)

app.include_router(health.router, tags=["health"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(machines.router, prefix="/machines", tags=["machines"])
app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
app.include_router(workers.router, prefix="/workers", tags=["workers"])