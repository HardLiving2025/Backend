# app/services/notification_service.py

from sqlalchemy.orm import Session
from datetime import datetime, date
from app.models.notification_logs import NotificationLog

# 기본 설정 (Settings 테이블 없을 때 적용)
DAILY_NOTIFICATION_LIMIT = 2          # 하루 최대 알림 개수
ALLOW_RISK_NOTIFICATION = True        # 위험 알림 활성화
ALLOW_MOOD_NOTIFICATION = True        # 감정 입력 알림 활성화

def can_send_notification(db: Session, user_id: int):
    # 오늘 보낸 알림 횟수 확인
    today = date.today()

    sent_count = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.user_id == user_id,
            NotificationLog.sent_at >= datetime.combine(today, datetime.min.time()),
            NotificationLog.sent_at <= datetime.combine(today, datetime.max.time())
        )
        .count()
    )

    if sent_count >= DAILY_NOTIFICATION_LIMIT:
        return False

    return True


def save_notification_log(db: Session, user_id: int, message_type: str):
    # 알림 발송 기록 저장
    log = NotificationLog(
        user_id=user_id,
        message_type=message_type,
        sent_at=datetime.now(),
        ignored_message=None,
        checked_message=None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
