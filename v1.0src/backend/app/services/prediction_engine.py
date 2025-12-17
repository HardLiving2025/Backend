import json
import os
import subprocess
import threading
from sqlalchemy.orm import Session
from datetime import date, timedelta

from app.models.app_usage_raw import AppUsageRaw
from app.models.prediction_logs import PredictionLog
from app.models.emotion_status_logs import EmotionStatusLog
from app.services.message_manager import MessageManager
from app.services.notification_service import (
    can_send_notification,
    save_notification_log,
)

# 현재 파일 위치: v0.6src/backend/app/services/prediction_engine.py
CURRENT_FILE = os.path.abspath(__file__)

# backend/app/services → backend/app → backend → v0.7src
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
        # Enforce Standard Window: Provide data for "Yesterday" (00:00~23:59)
        # to predict "Today".
        today = date.today()
        target_date = today - timedelta(days=1)

        rows = (
            db.query(AppUsageRaw)
            .filter(
                AppUsageRaw.user_id == user_id,
                AppUsageRaw.usage_date == target_date
            )
            .order_by(AppUsageRaw.usage_date.asc(), AppUsageRaw.start_time.asc())
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
        except Exception as e:
            print(f"[AI JSON ERROR] {e}")
            print(f"[AI STDOUT] {result.stdout.decode()}")
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

    # 5) 기분/상태 설명 상세 생성 (New API)
    @staticmethod
    def get_mood_details(emotion: str, status: str):
        # 1. Title Construction
        # Icon Map
        icons = {"GOOD": "😀", "NORMAL": "😐", "BAD": "😞"}
        emo_kr = {"GOOD": "좋음", "NORMAL": "평범", "BAD": "나쁨"}
        stat_kr = {"BUSY": "바쁨", "FREE": "여유로움"}
        
        icon = icons.get(emotion, "😐")
        e_text = emo_kr.get(emotion, emotion)
        s_text = stat_kr.get(status, status)
        
        title = f"{icon} {e_text} · {s_text}"
        
        # 2. Description Construction
        desc = ""
        if emotion == "BAD":
            if status == "FREE":
                desc = "오늘은 기분이 좋지 않고 여유로운 날이에요. 잠깐 산책을 해보는 것이 도움이 될 수 있어요."
            else: # BUSY
                desc = "기분이 저조한데 일정까지 바쁘시군요. 틈틈이 심호흡을 하며 마인드컨트롤이 필요해요."
        elif emotion == "GOOD":
            if status == "FREE":
                desc = "기분도 좋고 시간도 여유로운 완벽한 하루! 새로운 취미나 운동을 시작해보는 건 어떨까요?"
            else: # BUSY
                desc = "활기찬 에너지로 바쁜 하루도 거뜬히 이겨낼 수 있을 거예요! 다만 무리하지 않도록 주의하세요."
        else: # NORMAL
            if status == "FREE":
                desc = "차분하고 여유로운 하루네요. 읽고 싶었던 책을 읽거나 밀린 영화를 보는 건 어때요?"
            else: # BUSY
                desc = "평범한 하루지만 바쁜 일정이 기다리고 있네요. 차근차근 하나씩 해결해 나가보세요."
                
        return {"title": title, "description": desc}

    # 6) 추천 행동 생성
    @staticmethod
    def get_recommendations(level: str, emotion: str):
        if level == "SAFE":
            return [{
                "title": "🎉 훌륭해요!",
                "description": "오늘은 사용량이 적을 것으로 예상돼요. 이대로 좋은 습관을 유지하며 즐거운 하루 보내세요!"
            }]
            
        # Pool for CAUTION / DANGER
        pool = [
            {"title": "🚶‍♂️ 산책하기", "description": "잠깐 15분 정도 산책을 하면 숏폼 콘텐츠 사용 충동이 감소합니다."},
            {"title": "😌 휴식 취하기", "description": "저녁 시간대 전에 충분한 휴식을 취하면 과도한 앱 사용을 예방할 수 있습니다."},
            {"title": "📱 디지털 디톡스", "description": "20시 이후 스마트폰을 멀리 두고 독서나 명상 등 다른 활동을 해보세요."},
            {"title": "📖 독서하기", "description": "숏폼 콘텐츠 대신 책을 읽으면 수면의 질이 개선되고 마음의 안정을 찾을 수 있습니다."},
            {"title": "🧘 10분 명상", "description": "잠시 눈을 감고 호흡에 집중해보세요. 복잡한 머릿속을 비우는 데 큰 도움이 됩니다."},
            {"title": "🍵 따뜻한 차 마시기", "description": "따뜻한 차 한 잔의 여유를 가져보세요. 스마트폰 없이 오롯이 나에게 집중하는 시간입니다."},
            {"title": "🗣️ 친구와 대화하기", "description": "메신저 대신 직접 만나거나 전화로 대화해보세요. 소통의 즐거움을 느낄 수 있습니다."},
            {"title": "🖼️ 창밖 풍경 보기", "description": "잠시 스마트폰에서 눈을 떼고 멀리 있는 풍경을 바라보세요. 눈의 피로도 풀리고 기분 전환도 됩니다."},
            {"title": "📝 일기 쓰기", "description": "오늘 느낀 감정을 글로 적어보세요. 앱 사용 패턴을 스스로 돌아보는 계기가 됩니다."},
            {"title": "🎵 음악 감상", "description": "좋아하는 음악을 들으며 휴식을 취하세요. 스마트폰 화면을 보는 것보다 훨씬 더 힐링이 됩니다."}
        ]
        
        # Randomly pick 2 distinct items
        return random.sample(pool, 2)

    # 6) 최종 Prediction 로직 (Updated)
    @staticmethod
    def predict(user, db: Session, emotion: str = None, status: str = None):
        user_id = user.user_id

        # 0) Fetch emotion/status from DB if not provided
        if emotion is None or status is None:
            latest_log = (
                db.query(EmotionStatusLog)
                .filter(EmotionStatusLog.user_id == user_id)
                .order_by(EmotionStatusLog.created_at.desc())
                .first()
            )
            
            if latest_log:
                emotion = latest_log.emotion
                status = latest_log.status
            else:
                # Fallback: 데이터가 없으면 기본값 사용 (안전한 기본값)
                emotion = "GOOD"
                status = "FREE"

        # 1) 최근 사용 기록
        seq = PredictionEngine.fetch_recent_usage(user_id, db)

        # 2) AI 엔진 실행
        ai_result = PredictionEngine.call_ai_engine(emotion, status, seq)
        
        # Validate AI Result Structure
        required_keys = ["risk_analysis", "usage_prediction", "pattern_detection"]
        is_valid = all(k in ai_result for k in required_keys)

        if not is_valid:
            # Fallback Structure
            risk_analysis = {
                "level": "SAFE", # Enum: SAFE, CAUTION, DANGER
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
                "probability_percent": 0.0,
                "message": ""
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

            # [NEW] 4) Generate Korean Title & Description based on Level
            # Level: DANGER / CAUTION / SAFE
            level = risk_analysis.get("level", "SAFE")
            vuln_cat_raw = risk_analysis.get("vulnerable_category", "OTHER")
            
            # Map Category to Korean
            # Note: vulnerable_category might be "Instagram (SNS)" now due to above block
            # We want the main category for the sentence? Or just use as is?
            # User request: "기타/SNS/게임 중 위험도가 높은 것"
            # If we updated it to "Instagram (SNS)", we might want to just output that? 
            # Or stick to base categories? Let's use the full string if updated, else map base.
            
            cat_map = {"SNS": "SNS", "GAME": "게임", "OTHER": "기타"}
            
            # If vuln_cat_raw contains '(', it's already "App (Cat)". Let's use it directly or extract.
            # User asked: "(기타/SNS/게임 중 위험도가 높은 것)"
            # Let's try to map the base category if possible, or use the raw if it's specific.
            
            # Helper: Get Korean Category Name
            def get_kor_cat(c):
                # Clean up if needed, e.g. "Instagram (SNS)" -> "Instagram" or keep it?
                # User example just said "SNS".
                # If we have specific app, "Instagram" is better than "SNS".
                # Let's use the full text if it's specific, otherwise map base.
                if "(" in c: return c # Use "Instagram (SNS)"
                return cat_map.get(c, c)

            final_cat_kr = get_kor_cat(vuln_cat_raw)

            # Titles & Messages
            if level == "DANGER":
                risk_analysis["title"] = "위험도 높음"
                risk_analysis["message"] = f"오늘은 {final_cat_kr} 앱 과다 사용 위험도가 높은 날입니다."
            elif level == "CAUTION":
                risk_analysis["title"] = "위험도 보통"
                risk_analysis["message"] = f"오늘은 {final_cat_kr} 앱 사용에 주의가 필요합니다."
            else: # SAFE
                risk_analysis["title"] = "위험도 낮음"
                risk_analysis["message"] = "오늘은 위험도가 낮은 날입니다."

            # [NEW] 5) Generate Usage Prediction Message
            # "오늘은 (위험도가 높은 시간 1시간 범위, ex: 22~23)시에 (기타/SNS/게임 중 위험도가 높은 것) 사용 가능성이 높아요."
            if usage_prediction.get("has_prediction"):
                s_time = usage_prediction.get("start_time", "00:00") # "22:00"
                e_time = usage_prediction.get("end_time", "00:00")   # "23:00"
                u_cat = usage_prediction.get("target_category", "OTHER")
                u_cat_kr = get_kor_cat(u_cat)
                
                # Parse Hour
                try:
                    s_hour = int(s_time.split(":")[0])
                    e_hour = int(e_time.split(":")[0])
                    time_str = f"{s_hour}~{e_hour}"
                except:
                    time_str = f"{s_time}~{e_time}"
                
                usage_prediction["message"] = f"오늘은 {time_str}시에 {u_cat_kr} 앱 사용 가능성이 높아요."
            else:
                usage_prediction["message"] = ""
            
            # ---------------------------------------------

        # 3) Generate Recommendations (Backend Logic)
        # AI now returns DANGER/CAUTION/SAFE directly
        current_level = risk_analysis.get("level", "SAFE")
        
        recs = PredictionEngine.get_recommendations(current_level, emotion)
        
        # 5) Log to Database (New Request)
        try:
            # Risk Score/Level Handling
            r_score = float(risk_analysis.get("score", 0))
            r_level = risk_analysis.get("level", "SAFE")
            
            # [NEW] Parse Prediction Times if available
            r_start_time = None
            r_end_time = None
            
            if usage_prediction.get("has_prediction"):
                try:
                    from datetime import datetime, time
                    # We assume the prediction is for "Today" (analysis_date)
                    # analysis_date defaults to today+1 only if not found? 
                    # Actually, let's use date.today() as base since we are predicting for today usually.
                    base_date = date.today()
                    
                    st_str = usage_prediction.get("start_time", "00:00")
                    et_str = usage_prediction.get("end_time", "00:00")
                    
                    # Parse "HH:MM"
                    sh, sm = map(int, st_str.split(':'))
                    eh, em = map(int, et_str.split(':'))
                    
                    r_start_time = time(sh, sm)
                    r_end_time = time(eh, em)
                except Exception as ex:
                    print(f"[TIME PARSE ERROR] {ex}")
            
            # [NEW] Vulnerable App
            r_app = risk_analysis.get("vulnerable_category", "NONE")

            new_log = PredictionLog(
                user_id=user_id,
                input_emotion=emotion,
                input_status=status,
                risk_score=r_score,
                risk_level=r_level,
                risk_app=r_app,
                risk_start_time=r_start_time,
                risk_end_time=r_end_time
            )
            db.add(new_log)
            db.commit()
        except Exception as e:
            print(f"[LOGGING ERROR] {e}")
            db.rollback()



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
