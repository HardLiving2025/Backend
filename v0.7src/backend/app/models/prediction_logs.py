from sqlalchemy import Column, Integer, BigInteger, String, Float, Enum, DateTime, ForeignKey, func
from app.database import Base

class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    log_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    input_emotion = Column(String(20), nullable=False)
    input_status = Column(String(20), nullable=False)

    risk_score = Column(Float, nullable=False)
    risk_level = Column(Enum("SAFE", "CAUTION", "DANGER", name="risk_level_enum"), nullable=False)

    created_at = Column(DateTime, server_default=func.now())
