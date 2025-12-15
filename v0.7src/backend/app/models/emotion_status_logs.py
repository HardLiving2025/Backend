from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, func
from app.database import Base

class EmotionStatusLog(Base):
    __tablename__ = "emotion_status_logs"

    emotion_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    emotion = Column(Enum("GOOD", "NORMAL", "BAD", name="emotion_enum"), nullable=False)
    status = Column(Enum("BUSY", "FREE", name="status_enum"), nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())