from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.security import get_current_user
from app.models.notification_logs import NotificationLog

router = APIRouter()

@router.get("/")
def get_notifications(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    logs = db.query(NotificationLog).filter(
        NotificationLog.user_id == user.user_id
    ).order_by(NotificationLog.sent_at.desc()).all()

    return logs
