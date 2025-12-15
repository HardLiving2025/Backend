from pydantic import BaseModel
from typing import Optional

class MoodCreateRequest(BaseModel):
    emotion: str      # 'GOOD' | 'NORMAL' | 'BAD'
    status: str       # 'BUSY' | 'FREE'

class MoodCreateResponse(BaseModel):
    emotion_id: int
    emotion: str
    status: str
    created_at: str
