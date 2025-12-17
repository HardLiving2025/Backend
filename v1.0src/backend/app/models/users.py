# app/models/users.py

from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    google_id = Column(String(255), unique=True, nullable=False)
    nickname = Column(String(50), nullable=True)
    fcm_token = Column(String(255), nullable=True) # FCM Device Token
    created_at = Column(DateTime, server_default=func.now())