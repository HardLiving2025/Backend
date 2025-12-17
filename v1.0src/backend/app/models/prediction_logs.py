from sqlalchemy import Column, Integer, BigInteger, String, Float, Date, DateTime, Time, ForeignKey, func, Enum
from app.database import Base

class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    log_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    # 입력값
    input_emotion = Column(String(20), nullable=False)  # GOOD, NORMAL, BAD
    input_status = Column(String(20), nullable=False)   # BUSY, FREE

    # 위험도 분석
    risk_score = Column(Float, nullable=False)  # 0~100 (Float로 변경)
    risk_level = Column(Enum("SAFE", "CAUTION", "DANGER", name="risk_level_enum"), nullable=False) # 결과 (ENUM)
    
    risk_app = Column(String(50), nullable=True) # 예측된 위험도가 높은 앱
    
    risk_start_time = Column(Time, nullable=True) # 예측된 앱 사용 위험 시간대 시작 시간
    risk_end_time = Column(Time, nullable=True)   # 예측된 앱 사용 위험 시간대 종료 시간

    created_at = Column(DateTime, server_default=func.now())

