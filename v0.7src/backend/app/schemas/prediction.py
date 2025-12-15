from pydantic import BaseModel
from typing import Optional


class PredictionRequest(BaseModel):
    emotion: str      # 'GOOD' | 'NORMAL' | 'BAD'
    status: str       # 'BUSY' | 'FREE'



class RiskAnalysis(BaseModel):
    level: str
    score: int
    vulnerable_category: str
    condition: str
    message: str

class UsagePrediction(BaseModel):
    has_prediction: bool
    start_time: str
    end_time: str
    target_category: str
    probability_percent: float

class PatternDetection(BaseModel):
    detected: bool
    pattern_code: str
    alert_message: str

class PredictionResponse(BaseModel):
    user_id: int
    analysis_date: str
    
    risk_analysis: RiskAnalysis
    usage_prediction: UsagePrediction
    pattern_detection: PatternDetection
    
    hourly_forecast: list[float]
    recommendations: list[str]
