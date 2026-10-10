# api/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
     APP_NAME: str = "Lab Hacker API"
     ENV: str = "dev"
     DATABASE_URL: str = "postgresql+pg8000://lab:labpass@localhost:5432/labdb"
     JWT_SECRET: str = "change"
     JWT_ALGORITHM: str = "HS256"
     JWT_EXPIRE_MINUTES: int = 60

     class Config:
          env_file = "./.env"

settings = Settings()