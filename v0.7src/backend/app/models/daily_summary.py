from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, ForeignKey, func
from app.database import Base

class DailySummary(Base):
    __tablename__ = "daily_summary"

    summary_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    date = Column(Date, nullable=False)
    slot_index = Column(Integer, nullable=False)

    start_time = Column(DateTime)
    end_time = Column(DateTime)

    sns_ms = Column(Integer, default=0)
    game_ms = Column(Integer, default=0)
    other_ms = Column(Integer, default=0)
    total_usage_ms = Column(Integer, default=0)

    dominant_emotion = Column(String(20), nullable=True)
    status = Column(String(20), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
