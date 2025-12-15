from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    google_id = Column(String(255), unique=True, nullable=False)
    nickname = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())