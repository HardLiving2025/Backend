from pydantic import BaseModel
from typing import Optional, List





class RiskAnalysis(BaseModel):
    level: str
    score: int
    vulnerable_category: str
    condition: str
    message: str
    title: str = ""  # [NEW] For UI Title

class UsagePrediction(BaseModel):
    has_prediction: bool
    start_time: str
    end_time: str
    target_category: str
    probability_percent: float
    message: str = ""  # [NEW] For Time-based Message

class PatternDetection(BaseModel):
    detected: bool
    pattern_code: str
    alert_message: str

class Recommendation(BaseModel):
    title: str
    description: str

class PredictionResponse(BaseModel):
    user_id: int
    analysis_date: str
    
    risk_analysis: RiskAnalysis
    usage_prediction: UsagePrediction
    pattern_detection: PatternDetection
    
    hourly_forecast: list[float]
    recommendations: list[Recommendation]

class MoodDescriptionResponse(BaseModel):
    title: str
    description: str
