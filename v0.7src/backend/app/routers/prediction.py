from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.utils.security import get_current_user
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.prediction_engine import PredictionEngine
from app.models.users import User
from app.models.prediction_logs import PredictionLog

router = APIRouter()


@router.post("/today", response_model=PredictionResponse)
def predict_today(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    
    # Prediction Engine 실행
    result = PredictionEngine.predict(
        user=current_user,
        emotion=payload.emotion,
        status=payload.status,
        db=db
    )
    
    # DB 로깅
    try:
        log = PredictionLog(
            user_id=current_user.user_id,
            input_emotion=payload.emotion,
            input_status=payload.status,
            analysis_date=datetime.fromisoformat(result["analysis_date"]).date(),
            risk_score=result["risk_analysis"]["score"],
            risk_level=result["risk_analysis"]["level"],
            vulnerable_category=result["risk_analysis"].get("vulnerable_category"),
            peak_hour_start=result["usage_prediction"].get("start_time"),
            peak_hour_end=result["usage_prediction"].get("end_time"),
            pattern_code=result["pattern_detection"].get("pattern_code"),
            pattern_message=result["pattern_detection"].get("alert_message")
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"[Warning] Failed to log prediction: {e}")
        # 로깅 실패해도 예측 결과는 반환

    return result
