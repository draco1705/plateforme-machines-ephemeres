# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.routers import health, machines, reservations, ressources, users, workers

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

register_exception_handlers(app)

app.include_router(health.router, tags=["health"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(machines.router, prefix="/machines", tags=["machines"])
app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
app.include_router(workers.router, prefix="/workers", tags=["workers"])
app.include_router(ressources.router, prefix="/ressources", tags=["ressources"])