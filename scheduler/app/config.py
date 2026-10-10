from pydantic_settings import BaseSettings


class Settings(BaseSettings):
     DATABASE_URL: str 
     SCHEDULER_INTERVAL_SECONDS: int = 5
     BATCH_SIZE: int = 10

     class Config:
          env_file = ".env"
          extra = "ignore"

settings = Settings()