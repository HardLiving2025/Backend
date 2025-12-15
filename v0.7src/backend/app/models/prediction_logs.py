from sqlalchemy import Column, Integer, BigInteger, String, Float, Date, DateTime, ForeignKey, func, Text
from app.database import Base

class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    log_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    # 입력값
    input_emotion = Column(String(20), nullable=False)  # GOOD, NORMAL, BAD
    input_status = Column(String(20), nullable=False)   # BUSY, FREE
    
    # 분석 날짜
    analysis_date = Column(Date, nullable=False)

    # 위험도 분석
    risk_score = Column(Integer, nullable=False)  # 0-100
    risk_level = Column(String(20), nullable=False)  # LOW, MODERATE, HIGH
    vulnerable_category = Column(String(50), nullable=True)  # SNS, GAME, OTHER
    
    # 사용 예측 (피크 시간대)
    peak_hour_start = Column(String(10), nullable=True)  # "14:00"
    peak_hour_end = Column(String(10), nullable=True)    # "15:00"
    
    # 패턴 감지
    pattern_code = Column(String(50), nullable=True)     # PATTERN_NIGHT_OWL, NONE
    pattern_message = Column(Text, nullable=True)        # 패턴 설명

    created_at = Column(DateTime, server_default=func.now())

