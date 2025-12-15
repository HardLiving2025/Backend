import json
import os
import subprocess
import threading
from sqlalchemy.orm import Session
from datetime import date, timedelta

from app.models.app_usage_raw import AppUsageRaw
from app.services.message_manager import MessageManager
from app.services.notification_service import (
    can_send_notification,
    save_notification_log,
)

# 현재 파일 위치: v0.6src/backend/app/services/prediction_engine.py
CURRENT_FILE = os.path.abspath(__file__)

# backend/app/services → backend/app → backend → v0.6src
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(CURRENT_FILE)
        )
    )
)

# v0.7src/backend/ai_module/predict.py
AI_SCRIPT = os.path.join(BASE_DIR, "backend", "ai_module", "predict.py")
AI_SCRIPT = "/home/t25335/v0.7src/backend/ai_module/predict.py"

print("[DEBUG] USING prediction_engine.py AT:", __file__)
print("[DEBUG] BASE_DIR:", BASE_DIR)
print("[DEBUG] AI_SCRIPT:", AI_SCRIPT)


from app.utils.pattern_analyzer import analyze_patterns
import random

# Global Lock to prevent concurrent GPU access
_ai_execution_lock = threading.Lock()

class PredictionEngine:

    # 1) 최근 7일 사용 기록 조회
    @staticmethod
    def fetch_recent_usage(user_id: int, db: Session):
        end = date.today()
        start = end - timedelta(days=7)

        rows = (
            db.query(AppUsageRaw)
            .filter(
                AppUsageRaw.user_id == user_id,
                AppUsageRaw.usage_date.between(start, end)
            )
            .order_by(AppUsageRaw.usage_date.asc())
            .all()
        )

        return [
            {
                "usage_date": str(r.usage_date),
                "category": r.category,
                "package_name": r.package_name,
                "duration_ms": r.duration_ms,
                "start_time": str(r.start_time) if r.start_time else None,
            }
            for r in rows
        ]

    # 2) AI 엔진 subprocess 호출 (Existing logic kept for Risk Score)
    @staticmethod
    def call_ai_engine(emotion: str, status: str, seq_data: list):
        # predict_risk.py 에 JSON을 stdin으로 보내고 stdout에서 결과 받기
        
        input_json = json.dumps({
            "emotion": emotion,
            "status": status,
            "seq_data": seq_data,
        })

        try:
            # Acquire Lock before running subprocess
            # This serializes execution: User B waits until User A finishes.
            with _ai_execution_lock:
                result = subprocess.run(
                    ["python3", AI_SCRIPT],
                    input=input_json.encode(),
                    capture_output=True,
                    timeout=20
                )
        except Exception as e:
            print(f"[AI ERROR] {e}")
            return {"risk_score": 50.0}

        if result.returncode != 0:
            print("[AI ENGINE FAILED]", result.stderr.decode())
            return {"risk_score": 50.0}

        try:
            return json.loads(result.stdout.decode())
        except:
            return {"risk_score": 50.0}

    # 3) 위험 레벨 판정
    @staticmethod
    def determine_level(score: float):
        if score >= 0.70:
            return "DANGER"
        elif score >= 0.40:
            return "CAUTION"
        return "SAFE"

    # 4) 기분/상태 설명 생성
    @staticmethod
    def get_mood_description(emotion: str, status: str):
        # 파라미터에 따라 멘트 생성
        desc = ""
        if emotion == "GOOD":
            desc = "기분이 좋은 하루네요! "
        elif emotion == "NORMAL":
            desc = "평범하고 무난한 하루입니다. "
        elif emotion == "BAD":
            desc = "기분이 다소 저조한 날이네요. "
        
        if status == "BUSY":
            desc += "바쁜 일정 속에서도 틈틈이 휴식을 챙기세요."
        elif status == "FREE":
            desc += "여유로운 시간, 나만의 취미 생활을 즐겨보는 건 어떨까요?"
        else:
            desc += "오늘 하루도 화이팅하세요."
            
        return desc

    # 5) 추천 행동 생성
    @staticmethod
    def get_recommendations(level: str, emotion: str):
        recs = []
        if level == "DANGER":
            recs = ["디지털 디톡스 실천하기", "스마트폰 끄고 산책하기", "명상 10분 하기", "가족/친구와 대화하기"]
        elif level == "CAUTION":
            recs = ["알림 끄고 독서하기", "가벼운 스트레칭", "물 한 잔 마시고 휴식", "눈 건강 체조하기"]
        else: # SAFE
            if emotion == "BAD":
                recs = ["좋아하는 음악 듣기", "맛있는 간식 먹기", "짧은 낮잠", "일기 쓰기"]
            else:
                recs = ["새로운 취미 도전", "친구와 약속 잡기", "운동하기", "독서하기"]
        
        # Random pick 3-4
        return recs[:4]

    # 6) 최종 Prediction 로직 (Updated)
    @staticmethod
    def predict(user, emotion: str, status: str, db: Session):

        user_id = user.user_id

        # 1) 최근 사용 기록
        seq = PredictionEngine.fetch_recent_usage(user_id, db)

        # 2) AI 엔진 실행 (Risk Score)
        ai_result = PredictionEngine.call_ai_engine(emotion, status, seq)
        score = ai_result.get("risk_score", 50.0)
        hourly_forecast = ai_result.get("hourly_forecast", [])

        # 3) 위험 등급
        level = PredictionEngine.determine_level(score)

        # 4) 사용자 피드백 메시지 (Legacy Notification Logic)
        msg = MessageManager.get_message(level, emotion, status)

        # 5) 알림 빈도 제한 체크 (Settings 없이 기본 규칙 적용)
        try:
            if level in ["DANGER", "CAUTION"]:
                if can_send_notification(db, user_id):
                    save_notification_log(db, user_id, f"RISK_{level}")
        except Exception as e:
            print(f"[WARNING] Notification logging failed: {e}")

        # --- New Features ---
        
        # 6) Mood Description
        mood_desc = PredictionEngine.get_mood_description(emotion, status)
        
        # 7) Pattern & Time Analysis using internal Pattern Analyzer
        # We need to simulate 'Emotion Data' for the analyzer.
        # The analyzer expects a list of {date, emotion}. 
        # Since we are predicting for 'Today' (or based on recent history context), we can pass recent usage with their historical emotions?
        # Actually pattern analyzer finds correlations. 
        # If we pass current `seq` (7 days usage) and we don't have emotions for those days handy here (fetched only usage),
        # we should fetch emotions too.
        # But for simplicity, let's suggest patterns based on "Today's Emotion". 
        # Actually pattern analyzer takes HISTORY.
        # So we should fetch history emotions.
        # Let's quickly query last 7 days emotions.
        from app.models.daily_summary import DailySummary
        end = date.today()
        start = end - timedelta(days=7)
        emo_rows = db.query(DailySummary.date, DailySummary.dominant_emotion).filter(
             DailySummary.user_id == user_id,
             DailySummary.date.between(start, end)
        ).all()
        
        emo_data = [{"date": str(r.date), "emotion": r.dominant_emotion} for r in emo_rows if r.dominant_emotion]
        
        # Run Analyzer
        # It returns list of {title, content}
        patterns = analyze_patterns(seq, emo_data)
        
        # Time Prediction
        # Helper to extract time specific string? 
        # Pattern analyzer returns general patterns. 
        # Required: "어느 시간대에 어떤 앱 사용 가능성이 높은 것인지"
        # If pattern analyzer returned a time-based pattern (e.g. "20-21시 집중 사용"), we can stick it here.
        # Or we can create a specific string based on logic.
        # Let's extract the first "Time" related pattern from `patterns` if available.
        # Or assume Peak Hour from usage data.
        time_pred = "현재 시간대 분석 정보가 부족합니다."
        for p in patterns:
            if "집중 사용" in p["title"]:
                time_pred = f"오늘 {p['title']} 가능성이 높습니다. ({p['content']})"
                break
        
        # 8) Recommendations
        recs = PredictionEngine.get_recommendations(level, emotion)

        return {
            "risk_score": score,
            "risk_level": level,
            "message_title": msg["title"],
            "message_body": msg["body"],
            "hourly_forecast": hourly_forecast,
            # New Keys
            "mood_description": mood_desc,
            "patterns": patterns,
            "time_prediction": time_pred,
            "recommendations": recs
        }
