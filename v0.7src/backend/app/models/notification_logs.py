from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey, Boolean, func
from app.database import Base
from datetime import datetime

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    noti_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    message_type = Column(String(50), nullable=False)
    message_body = Column(Text, nullable=False)

    risk_level = Column(Enum("SAFE", "CAUTION", "DANGER", name="risk_level_enum"), nullable=False) 
    
    is_read = Column(Boolean, default=False)      # 사용자가 클릭해서 읽었는지
    response_action = Column(String(50), nullable=True) # 사용자의 후속 행동 (예: 'APP_OPEN', 'DISMISS')

    sent_at = Column(DateTime, server_default=func.now())
