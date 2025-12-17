from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, ForeignKey, func, UniqueConstraint
from app.database import Base

class AppUsageRaw(Base):
    __tablename__ = "app_usage_raw"

    raw_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    usage_date = Column(Date, nullable=False)

    slot_index = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False) 
    end_time = Column(DateTime, nullable=False)

    package_name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)

    duration_ms = Column(BigInteger, default=0)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'usage_date', 'slot_index', 'package_name', name='uix_user_usage_slot_pkg'),
    )
