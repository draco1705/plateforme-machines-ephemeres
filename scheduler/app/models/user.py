# api/app/models/user.py
from sqlalchemy import Column, Integer, String, DateTime, func, Index
from app.database import Base 

class User(Base):
     __tablename__ = "users"
     __table_args__ = (
        Index("ix_users_email", "email", unique=True),
    )
     id            = Column(Integer, primary_key=True)
     email         = Column(String(255), unique=True, nullable=False, index=True)
     password_hash = Column(String(255), nullable=False)
     role          = Column(String(20), default="user") 
     created_at    = Column(DateTime(timezone=True), server_default=func.now())