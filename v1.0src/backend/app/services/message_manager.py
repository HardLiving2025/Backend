import os
import json
import requests
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.users import User
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_nightly_notifications():
    
    # 매일 실행되는 배치 작업
    # 모든 유저(혹은 대상 유저)에 대해 알림 메시지를 생성하고 전송
    
    logger.info("Starting nightly notification job...")
    
    # Deferred Import to avoid Circular Import
    from app.services.notification_service import get_nightly_notification_message
    
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()

        for user in users:
            try:
                if not user.fcm_token:
                    continue
                
                logger.info(f"Processing notification for user {user.user_id}")
                
                msg_data = get_nightly_notification_message(db, user)
                
                title = msg_data.get("title")
                body = msg_data.get("body")
                
                if title and body:
                    success = MessageManager.send_push_notification(user.fcm_token, title, body)
                    if success:
                        logger.info(f"Notification sent to user {user.user_id}")
                    else:
                        logger.warning(f"Failed to send notification to user {user.user_id}")
            
            except Exception as e:
                logger.error(f"Error processing user {user.user_id}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error in nightly notification job: {e}")
    finally:
        db.close()
        logger.info("Nightly notification job finished.")


class SchedulerService:
    scheduler = BackgroundScheduler()

    @staticmethod
    def start():
        if SchedulerService.scheduler.running:
            return

        SchedulerService.scheduler.add_job(
            send_nightly_notifications, 
            'cron', 
            hour=23, 
            minute=0, 
            id='nightly_notification'
        )
        
        SchedulerService.scheduler.start()
        logger.info("[MessageManager] Scheduler started. Nightly job scheduled for 23:00.")

    @staticmethod
    def stop():
        if SchedulerService.scheduler.running:
            SchedulerService.scheduler.shutdown()

class MessageManager:

    # FCM HTTP v1 API URL
    # PROJECT_ID는 serviceAccountKey.json에서 읽거나 환경변수로 설정
    FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']

    @staticmethod
    def construct_message(risk_level: str, input_emotion: str = None, risk_app: str = None, risk_start_time=None, risk_end_time=None):
        
        # prediction_logs 테이블 데이터를 기반으로 알림 메시지(title, body)를 생성
        # title : 현재 시각 
        # body : 조건에 따른 메시지 (DANGER/CAUTION은 가능한 후보군 중 랜덤 선택)
        from datetime import datetime
        import random
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = current_time
        body = ""

        # 시간 포맷팅 함수
        def format_time(t):
            if t:
                return t.strftime("%H:%M")
            return ""

        # Translate to Korean
        if risk_app:
            if risk_app == "GAME":
                risk_app = "게임"
            elif risk_app == "OTHER":
                risk_app = "기타"

        start_str = format_time(risk_start_time)
        end_str = format_time(risk_end_time)

        if risk_level == "DANGER":
            candidates = []

            # 1. Emotion-based msg
            if input_emotion == "BAD" and risk_app:
                candidates.append(f"기분이 좋지 않은 상태에서 {risk_app} 앱 사용이 감지되었습니다. 잠시 스마트폰을 내려놓고 산책을 해보는 건 어떨까요?")
            
            # 2. Time-based msg
            if risk_app and start_str and end_str:
                candidates.append(f"패턴 분석 결과, {start_str}부터 {end_str} 동안 과도한 {risk_app} 앱 사용이 시작될 가능성이 높습니다. 주의해주세요.")

            # 3. App-based msg
            if risk_app:
                candidates.append(f"위험 시간대에 {risk_app} 앱 사용을 이어가실 가능성이 높아요. 이 시간대의 휴대폰 사용은 수면 리듬을 가장 많이 무너뜨립니다.")
            
            # Select Randomly if candidates exist
            if candidates:
                body = random.choice(candidates)
            else:
                # Fallback for DANGER
                body = "현재 상태에서는 과몰입 위험이 높아요. 잠시 쉬었다가 다시 시작해보세요."

        elif risk_level == "CAUTION":
            candidates = []

            # 1. Time-based msg
            if risk_app and start_str and end_str:
                candidates.append(f"패턴 분석 결과, {start_str}부터 {end_str} 동안 {risk_app} 앱 사용량이 높아질 수 있어요. 잠시 쉬었다가 다시 시작해보는 건 어떨까요?")

            # 2. App-based msg
            if risk_app:
                candidates.append(f"주의 시간대에 {risk_app} 앱 사용을 이어가실 가능성이 높아요. 이 시간대의 휴대폰 사용은 더 좋지 않은 휴대폰 사용 습관을 유발할 수 있습니다.")

            # Select Randomly
            if candidates:
                body = random.choice(candidates)
            else:
                # Fallback for CAUTION
                body = "지금은 사용량이 조금 높은 편이에요."

        else: # SAFE
            body = "좋아요! 건강한 스마트폰 사용 패턴을 유지하고 있어요. 이대로 좋은 습관을 유지하며 좋은 하루 보내세요!"

        return {"title": title, "body": body}

    @staticmethod
    def _get_access_token():

        # serviceAccountKey.json을 사용하여 OAuth2 Access Token을 발급받습니다.
        key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "serviceAccountKey.json")
        
        if not os.path.exists(key_path):
            print(f"[Warning] serviceAccountKey.json not found at {key_path}")
            return None, None

        try:
            creds = service_account.Credentials.from_service_account_file(
                key_path, scopes=MessageManager.SCOPES
            )
            creds.refresh(Request())
            return creds.token, creds.project_id
        except Exception as e:
            print(f"[Error] Failed to get access token: {e}")
            return None, None

    @staticmethod
    def send_push_notification(fcm_token: str, title: str, body: str):
        
        # FCM HTTP v1 API를 사용하여 푸시 알림을 전송합니다.
        if not fcm_token:
            print("[Warning] No FCM token provided")
            return False

        access_token, project_id = MessageManager._get_access_token()
        if not access_token or not project_id:
            print("[Error] Cannot send notification: missing credentials")
            return False

        # 메시지 구성
        message = {
            "message": {
                "token": fcm_token,
                "notification": {
                    "title": title,
                    "body": body
                },
                # 안드로이드 설정 (선택사항)
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": "screen_comma_alert_channel" # 앱에서 설정한 채널 ID
                    }
                }
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = MessageManager.FCM_ENDPOINT.format(project_id=project_id)

        try:
            response = requests.post(url, headers=headers, json=message)
            if response.status_code == 200:
                print(f"[Success] Notification sent to {fcm_token[:10]}...")
                return True
            else:
                print(f"[Error] FCM Send Failed: {response.text}")
                return False
        except Exception as e:
            print(f"[Error] HTTP Request failed: {e}")
            return False
