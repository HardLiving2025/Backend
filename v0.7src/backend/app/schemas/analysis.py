from pydantic import BaseModel
from typing import List, Optional, Dict


class UsageCategorySummary(BaseModel):
    category: str
    total_ms: int


class YesterdaySummaryResponse(BaseModel):
    total_usage_ms: int
    avg_7days_ms: float
    diff_ms: float
    emotion: Optional[str] = None
    status: Optional[str] = None


class EmotionStatItem(BaseModel):
    emotion: str
    category: str
    total_ms: int


class UsageByEmotionResponse(BaseModel):
    stats: List[EmotionStatItem]


class UsageByEmotionStatusResponse(BaseModel):
    # { "GOOD": { "BUSY": 1000, "FREE": 2000 }, "NORMAL": ... }
    yesterday: Dict[str, Dict[str, int]]
    week_1: Dict[str, Dict[str, int]]
    week_2: Dict[str, Dict[str, int]]
    month_1: Dict[str, Dict[str, int]]
