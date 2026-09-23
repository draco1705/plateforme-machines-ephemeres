# api/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
     APP_Name: str = "Lab Hacker API"
     ENV: str = "dev"
     DATABASE_URL: str = "postgresql://lab:lab@localhost:5432/labdb"
     JWT_SECRET: str = "change"
     JWT_ALGORITHM: str = "HS256"
     JWT_EXPIRE_MINUTES: int = 60

     class Config:
          env_file = "./.env"

settings = Settings()