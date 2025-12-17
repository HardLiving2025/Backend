# app/services/notification_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func
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


def save_notification_log(db: Session, user_id: int, message_type: str, message_body: str, risk_level: str):
    # 알림 발송 기록 저장
    log = NotificationLog(
        user_id=user_id,
        message_type=message_type,
        message_body=message_body,
        risk_level=risk_level,
        sent_at=datetime.now()
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_recent_notifications(db: Session, user_id: int):
    recent_logs = db.query(NotificationLog).filter(
        NotificationLog.user_id == user_id
    ).order_by(NotificationLog.sent_at.desc()).limit(3).all()

    recent_items = [
        {
            "noti_id": log.noti_id,
            "message_type": log.message_type,
            "message_body": log.message_body,
            "sent_at": log.sent_at
        }
        for log in recent_logs
    ]
    
    return {
        "recent_notifications": recent_items
    }


def get_nightly_notification_message(db: Session, user):
    from app.services.prediction_engine import PredictionEngine
    from app.services.message_manager import MessageManager

    # 1. Get Prediction (Risk Level)
    # predict() : 감정 상태 로그가 없으면 최근 로그를 가져옴
    prediction = PredictionEngine.predict(user=user, db=db)
    
    risk_data = prediction.get("risk_analysis", {})
    level = risk_data.get("level", "SAFE")
    emotion = risk_data.get("condition", "NORMAL")
    
    # 2. Get Message (risk_level 기준)
    # 메시지 구성에 따라 pattern, risk_app, risk_start_time, risk_end_time 추출
    # Correct extraction based on prediction_engine output structure
    
    # risk_app is in risk_analysis['vulnerable_category']
    risk_app = risk_data.get("vulnerable_category")
    
    if risk_app == "GAME":
        risk_app = "게임"
    elif risk_app == "OTHER":
        risk_app = "기타"
    # SNS는 그대로 "SNS"
    # 만약 "Instagram (SNS)" 같은 형태라면 그대로 둠 or 필요시 파싱.
    # 요청사항: "SNS는 'SNS' 그대로 받아들이되, GAME은 '게임'으로, OTHER은 '기타'로"
    # 단순 매핑만 추가함.

    # Times are in usage_prediction
    usage_pred = prediction.get("usage_prediction", {})
    start_str = usage_pred.get("start_time")
    end_str = usage_pred.get("end_time")
    
    from datetime import datetime, time
    
    def parse_time(t_str):
        if not t_str: return None
        try:
            h, m = map(int, t_str.split(':'))
            return time(h, m)
        except:
            return None

    start_time = parse_time(start_str)
    end_time = parse_time(end_str)

    msg_data = MessageManager.construct_message(
        risk_level=level, 
        input_emotion=emotion, 
        risk_app=risk_app,
        risk_start_time=start_time,
        risk_end_time=end_time
    )
    
    # 3. notification_logs 테이블에 저장
    save_notification_log(
        db=db,
        user_id=user.user_id,
        message_type=msg_data["title"],
        message_body=msg_data["body"],
        risk_level=level
    )

    return {
        "title": msg_data["title"],
        "body": msg_data["body"],
        "risk_level": level
    }
