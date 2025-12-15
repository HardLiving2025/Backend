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

    # 1) 최근 사용 기록 조회
    @staticmethod
    def fetch_recent_usage(user_id: int, db: Session):
        end = date.today()
        # User requested minimizing data. 2 days ensures we have >= 24h context.
        start = end - timedelta(days=2) 

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

    # ... (call_ai_engine, determine_level, get_mood_description, get_recommendations omitted - no changes needed)


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

        # 2) AI 엔진 실행
        # ai_result now contains: user_id, analysis_date, risk_analysis, usage_prediction, pattern_detection
        ai_result = PredictionEngine.call_ai_engine(emotion, status, seq)
        
        # Fallback if AI fails or returns legacy/error
        if "risk_analysis" not in ai_result:
            # Construct fallback structure
            risk_analysis = {
                "level": "LOW",
                "score": 0,
                "vulnerable_category": "NONE",
                "condition": emotion,
                "message": "AI 분석을 수행할 수 없습니다."
            }
            usage_prediction = {
                "has_prediction": False,
                "start_time": "00:00",
                "end_time": "00:00",
                "target_category": "NONE",
                "probability_percent": 0.0
            }
            pattern_detection = {
                "detected": False,
                "pattern_code": "NONE",
                "alert_message": ""
            }
            hourly_forecast = []
        else:
            risk_analysis = ai_result["risk_analysis"]
            usage_prediction = ai_result["usage_prediction"]
            pattern_detection = ai_result["pattern_detection"]
            hourly_forecast = ai_result.get("hourly_forecast", [])
            
            # --- [NEW] Identify Specific Vulnerable App ---
            # AI gives 'SNS', we want 'Instagram' from seq history
            vuln_cat = risk_analysis.get("vulnerable_category", "NONE")
            
            if vuln_cat not in ["NONE", "OTHER"]:
                # Filter sequence for this category
                # seq item: {category, package_name, duration_ms}
                relevant_apps = {}
                for item in seq:
                    # Clean comparison (item['category'] might be 'SNS' or logic needed?)
                    # Assuming item['category'] aligns with model output
                    if item.get("category") == vuln_cat:
                        pkg = item.get("package_name", "Unknown")
                        dur = item.get("duration_ms", 0)
                        relevant_apps[pkg] = relevant_apps.get(pkg, 0) + dur
                
                # Find max
                if relevant_apps:
                    top_app = max(relevant_apps, key=relevant_apps.get)
                    # Clean Name: com.instagram.android -> Instagram
                    simple_name = top_app.split('.')[-1].capitalize()
                    
                    # Update Risk Analysis
                    risk_analysis["vulnerable_category"] = f"{simple_name} ({vuln_cat})"
                    
                    # Update Usage Prediction too if matches
                    if usage_prediction.get("target_category") == vuln_cat:
                         usage_prediction["target_category"] = f"{simple_name} ({vuln_cat})"
            # ---------------------------------------------

        # 3) Generate Recommendations (Backend Logic)
        level_map = {"HIGH": "DANGER", "MODERATE": "CAUTION", "LOW": "SAFE"}
        legacy_level = level_map.get(risk_analysis["level"], "SAFE")
        
        recs = PredictionEngine.get_recommendations(legacy_level, emotion)
        
        # 4) Construct Final Response
        return {
            "user_id": user_id,
            "analysis_date": ai_result.get("analysis_date", str(date.today() + timedelta(days=1))),
            "risk_analysis": risk_analysis,
            "usage_prediction": usage_prediction,
            "pattern_detection": pattern_detection,
            "hourly_forecast": hourly_forecast, # For Graph
            "recommendations": recs, # Value add
        }
