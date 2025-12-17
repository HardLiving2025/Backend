from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.security import get_current_user
from app.schemas.notifications import (
    NotificationRecentResponse, 
)
from app.services.notification_service import (
    get_recent_notifications,
    get_nightly_notification_message
)
from app.schemas.notifications import NotificationMessageResponse


router = APIRouter()


@router.get("/message", response_model=NotificationMessageResponse)
def get_notification_message(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 11PM 알림용 메시지 생성:
    # AI 예측 결과(Risk Level)를 기반으로 MessageManager에서 메시지를 가져옵니다.
    return get_nightly_notification_message(db, user)


@router.get("/recent", response_model=NotificationRecentResponse)
def get_recent_three_notifications(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_recent_notifications(db, user.user_id)
