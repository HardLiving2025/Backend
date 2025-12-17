from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class DailySummaryBase(BaseModel):
    user_id: int
    date: date
    slot_index: int
    start_time: datetime
    end_time: datetime
    
    sns_ms: int
    game_ms: int
    other_ms: int
    total_usage_ms: int
    
    dominant_emotion: Optional[str] = None
    status: Optional[str] = None


class DailyUsageInput(BaseModel):
    usage_date: date
    time_slot: str  # "HH:MM" format
    package: dict[str, int]  # package_name: duration_ms

class DailySummaryResponse(DailySummaryBase):
    summary_id: int
    created_at: datetime

    class Config:
        from_attributes = True
