from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import get_current_user
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.prediction_engine import PredictionEngine
from app.models.users import User

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

    return result
