from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.utils.security import get_current_user
from app.services.daily_summary_service import DailySummaryService

from typing import List
from app.models.daily_summary import DailySummary
from app.schemas.daily_summary import DailySummaryResponse, DailyUsageInput

router = APIRouter()


# 프론트엔드 사용 데이터 업로드 및 요약 생성
@router.post("/upload")
def upload_daily_usage(data: List[DailyUsageInput],
                       db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    
    count = DailySummaryService.process_frontend_data(user.user_id, data, db)
    return {"message": "usage data processed", "count": count}


# 수동으로 특정 날짜 요약 생성하기
@router.post("/generate/{date_str}")
def generate_summary(date_str: str, 
                     db: Session = Depends(get_db), 
                     user=Depends(get_current_user)):

    target_date = date.fromisoformat(date_str)
    DailySummaryService.generate_summary_for_date(user.user_id, target_date, db)

    return {"message": "summary generated", "date": date_str}


@router.get("/{date_str}", response_model=List[DailySummaryResponse])
def get_daily_summary(date_str: str,
                      db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    target_date = date.fromisoformat(date_str)
    
    summaries = db.query(DailySummary).filter(
        DailySummary.user_id == user.user_id,
        DailySummary.date == target_date
    ).order_by(DailySummary.slot_index.asc()).all()
    
    return summaries


# 어제 요약 생성
@router.post("/generate-yesterday")
def generate_yesterday(db: Session = Depends(get_db),
                       user=Depends(get_current_user)):

    DailySummaryService.generate_yesterday(user.user_id, db)
    return {"message": "yesterday summary generated"}

