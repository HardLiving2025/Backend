from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.utils.security import get_current_user
from app.services.analysis_service import (
    get_average_usage_stats,
    get_usage_by_emotion_average,
    get_app_ratios_by_emotion,
    get_major_patterns,
    get_usage_by_emotion_status,
)

router = APIRouter()


# 1) 감정별 평균 사용량 (SNS, GAME, OTHER)
@router.get("/usage-by-emotion-average")
def usage_by_emotion_average(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_usage_by_emotion_average(db, current_user.user_id)


# 2) 앱별 감정 비율 (Top 5)
@router.get("/app-ratios-by-emotion")
def app_ratios_by_emotion(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_app_ratios_by_emotion(db, current_user.user_id)


# 3) 구간별(어제, 1주, 2주, 1달) 시간대별 평균 사용량
@router.get("/usage-by-slot-average")
def usage_by_slot_average(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_average_usage_stats(db, current_user.user_id)



# 4) 감정별 상태별 평균 사용량
@router.get("/usage-by-emotion-status")
def usage_by_emotion_status(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_usage_by_emotion_status(db, current_user.user_id)


# 5) 주요 패턴 분석
@router.get("/major-patterns")
def major_patterns(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_major_patterns(db, current_user.user_id)

