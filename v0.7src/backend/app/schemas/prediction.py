from pydantic import BaseModel
from typing import Optional


class PredictionRequest(BaseModel):
    emotion: str      # 'GOOD' | 'NORMAL' | 'BAD'
    status: str       # 'BUSY' | 'FREE'


class PredictionResponse(BaseModel):
    risk_score: float
    risk_level: str
    message_title: str
    message_body: str
    
    # New fields
    mood_description: str
    patterns: list[dict] # {title, content}
    time_prediction: str
    recommendations: list[str]
