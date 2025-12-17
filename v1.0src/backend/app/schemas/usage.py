from pydantic import BaseModel
from typing import Dict, List, Optional

class UsageDaySchema(BaseModel):
    usage_date: str  # "YYYY-MM-DD"
    time_slot: str   # "HH:MM" (Start time of the 30-min slot, e.g., "00:00", "00:30")
    package_data: Dict[str, int]  # {"package_name": duration_ms}

class UsageBatchResponse(BaseModel):
    saved_count: int
    message: str
