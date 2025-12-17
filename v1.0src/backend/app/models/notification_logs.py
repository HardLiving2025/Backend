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
    sent_at = Column(DateTime, server_default=func.now())
