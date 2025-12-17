from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.utils.security import get_current_user
from app.schemas.prediction import PredictionResponse, MoodDescriptionResponse
from app.services.prediction_engine import PredictionEngine
from app.models.users import User
from app.models.emotion_status_logs import EmotionStatusLog

router = APIRouter()


@router.get("/today", response_model=PredictionResponse)
def predict_today(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    
    # [NEW] Fetch latest Emotion/Status from DB
    latest_log = (
        db.query(EmotionStatusLog)
        .filter(EmotionStatusLog.user_id == current_user.user_id)
        .order_by(EmotionStatusLog.created_at.desc())
        .first()
    )
    
    if latest_log:
        emotion = latest_log.emotion
        status = latest_log.status
    else:
        # Fallback default
        emotion = "NORMAL"
        status = "FREE"

    # Prediction Engine 실행 (DB 로깅은 Engine 내부에서 처리됨)
    result = PredictionEngine.predict(
        user=current_user,
        emotion=emotion,
        status=status,
        db=db
    )
    
    return result

@router.get("/description", response_model=MoodDescriptionResponse)
def get_mood_description(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    기분과 상태를 DB에서 조회하여
    제목(아이콘 포함)과 친절한 설명 멘트를 반환합니다.
    """
    latest_log = (
        db.query(EmotionStatusLog)
        .filter(EmotionStatusLog.user_id == current_user.user_id)
        .order_by(EmotionStatusLog.created_at.desc())
        .first()
    )
    
    if latest_log:
        emotion = latest_log.emotion
        status = latest_log.status
    else:
        emotion = "NORMAL"
        status = "FREE"

    return PredictionEngine.get_mood_details(emotion, status)
