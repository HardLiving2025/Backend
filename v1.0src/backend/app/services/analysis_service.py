# app/services/analysis_service.py

from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.daily_summary import DailySummary
from app.models.emotion_status_logs import EmotionStatusLog
from app.models.app_usage_raw import AppUsageRaw
from app.utils.pattern_analyzer import analyze_patterns, get_app_name
from sqlalchemy import func


def get_average_usage_stats(db: Session, user_id: int):
    # 어제, 1주일, 2주일, 1개월 평균 데이터
    today = date.today()
    periods = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week_1": (today - timedelta(days=7), today - timedelta(days=1)),
        "week_2": (today - timedelta(days=14), today - timedelta(days=1)),
        "month_1": (today - timedelta(days=30), today - timedelta(days=1)),
    }

    response = {}

    for label, (start_date, end_date) in periods.items():
        rows = (
            db.query(
                DailySummary.slot_index,
                func.min(DailySummary.start_time).label("start_time"), # 대표 시간 (가장 빠른 것)
                func.min(DailySummary.end_time).label("end_time"),
                func.avg(DailySummary.sns_ms).label("avg_sns"),
                func.avg(DailySummary.game_ms).label("avg_game"),
                func.avg(DailySummary.other_ms).label("avg_other"),
                func.avg(DailySummary.total_usage_ms).label("avg_total")
            )
            .filter(
                DailySummary.user_id == user_id,
                DailySummary.date >= start_date,
                DailySummary.date <= end_date
            )
            .group_by(DailySummary.slot_index)
            .all()
        )

        # 0~47 슬롯 초기화
        slot_data = []
        for i in range(48):
            slot_data.append({
                "slot": i,
                "start_time": None,
                "end_time": None,
                "sns": 0,
                "game": 0,
                "other": 0,
                "total": 0
            })

        for row in rows:
            idx = row.slot_index
            # Time 객체 -> 문자열 변환 (HH:MM)
            s_time = row.start_time.strftime("%H:%M") if row.start_time else None
            e_time = row.end_time.strftime("%H:%M") if row.end_time else None
            
            # 만약 start_time이 datetime이라면 time() 추출 필요할 수 있으나, 
            # MySQL에서 DateTime 컬럼이면 python datetime 객체로 넘어옴.
            
            slot_data[idx] = {
                "slot": idx,
                "start_time": s_time,
                "end_time": e_time,
                "sns": int(row.avg_sns or 0),
                "game": int(row.avg_game or 0),
                "other": int(row.avg_other or 0),
                "total": int(row.avg_total or 0),
            }
        
        response[label] = slot_data

    return response



def get_usage_by_emotion_average(db: Session, user_id: int):
    # 감정별(GOOD, NORMAL, BAD) 평균 사용량 (SNS, GAME, OTHER)
    # 어제, 1주일, 2주일, 1개월 평균 데이터
    today = date.today()
    periods = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week_1": (today - timedelta(days=7), today - timedelta(days=1)),
        "week_2": (today - timedelta(days=14), today - timedelta(days=1)),
        "month_1": (today - timedelta(days=30), today - timedelta(days=1)),
    }

    response = {}

    for label, (start_date, end_date) in periods.items():
        rows = (
            db.query(
                DailySummary.dominant_emotion,
                func.avg(DailySummary.sns_ms).label("avg_sns"),
                func.avg(DailySummary.game_ms).label("avg_game"),
                func.avg(DailySummary.other_ms).label("avg_other")
            )
            .filter(
                DailySummary.user_id == user_id,
                DailySummary.date >= start_date,
                DailySummary.date <= end_date,
                DailySummary.dominant_emotion.isnot(None),
                DailySummary.dominant_emotion != ""
            )
            .group_by(DailySummary.dominant_emotion)
            .all()
        )
        
        period_result = {
            "GOOD": {"SNS": 0, "GAME": 0, "OTHER": 0},
            "NORMAL": {"SNS": 0, "GAME": 0, "OTHER": 0},
            "BAD": {"SNS": 0, "GAME": 0, "OTHER": 0},
        }
        
        for r in rows:
            emo = r.dominant_emotion
            if emo in period_result:
                period_result[emo]["SNS"] = int(r.avg_sns or 0)
                period_result[emo]["GAME"] = int(r.avg_game or 0)
                period_result[emo]["OTHER"] = int(r.avg_other or 0)
        
        response[label] = period_result

    return response


def get_app_ratios_by_emotion(db: Session, user_id: int):
    # 앱별 감정 비율 (Top 5)
    # 어제, 1주일, 2주일, 1개월 데이터
    today = date.today()
    periods = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week_1": (today - timedelta(days=7), today - timedelta(days=1)),
        "week_2": (today - timedelta(days=14), today - timedelta(days=1)),
        "month_1": (today - timedelta(days=30), today - timedelta(days=1)),
    }

    response = {}

    for label, (start_date, end_date) in periods.items():
        # Correct Join: AppUsageRaw <-> DailySummary on (user_id, date, slot_index)
        # This avoids Cartesian product if there are multiple slots per day.
        stats = (
            db.query(
                DailySummary.dominant_emotion,
                AppUsageRaw.package_name,
                func.sum(AppUsageRaw.duration_ms).label("total_ms")
            )
            .join(
                DailySummary,
                (AppUsageRaw.user_id == DailySummary.user_id) &
                (AppUsageRaw.usage_date == DailySummary.date) &
                (AppUsageRaw.slot_index == DailySummary.slot_index)
            )
            .filter(
                AppUsageRaw.user_id == user_id,
                AppUsageRaw.usage_date >= start_date,
                AppUsageRaw.usage_date <= end_date,
                DailySummary.dominant_emotion.isnot(None)
            )
            .group_by(DailySummary.dominant_emotion, AppUsageRaw.package_name)
            .all()
        )
        
        # Process in Python to get Top 5 per emotion
        data_by_emotion = {"GOOD": [], "NORMAL": [], "BAD": []}
        
        for em, pkg, ms in stats:
            if em in data_by_emotion:
                data_by_emotion[em].append({
                    "app": pkg,
                    "app_name": get_app_name(pkg),
                    "ms": int(ms)
                })
                
        # Sort and take top 5
        period_result = {}
        for emo, app_list in data_by_emotion.items():
            sorted_list = sorted(app_list, key=lambda x: x["ms"], reverse=True)
            period_result[emo] = sorted_list[:5]
        
        response[label] = period_result
        
    return response


def get_major_patterns(db: Session, user_id: int):
    # 주요 패턴 분석 (AI/Statistical)
    # 어제, 1주일, 2주일, 1개월 평균 데이터
    today = date.today()
    periods = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week_1": (today - timedelta(days=7), today - timedelta(days=1)),
        "week_2": (today - timedelta(days=14), today - timedelta(days=1)),
        "month_1": (today - timedelta(days=30), today - timedelta(days=1)),
    }
    
    response = {}

    for label, (start_date, end_date) in periods.items():
        usage_rows = (
            db.query(AppUsageRaw)
            .filter(
                AppUsageRaw.user_id == user_id,
                AppUsageRaw.usage_date >= start_date,
                AppUsageRaw.usage_date <= end_date
            )
            .all()
        )
        
        emotion_rows = (
            db.query(DailySummary.date, DailySummary.dominant_emotion)
            .filter(
                DailySummary.user_id == user_id,
                DailySummary.date >= start_date,
                DailySummary.date <= end_date,
                DailySummary.dominant_emotion.isnot(None)
            )
            .all()
        )
        
        usage_data = [
            {
                "date": r.usage_date,
                "category": r.category,
                "package_name": r.package_name,
                "duration_ms": r.duration_ms,
                "start_time": r.start_time
            }
            for r in usage_rows
        ]
        
        emotion_data = [
            {
                "date": r.date,
                "emotion": r.dominant_emotion
            }
            for r in emotion_rows
        ]
        
        response[label] = analyze_patterns(usage_data, emotion_data)
        
    return response

def get_usage_by_emotion_status(db: Session, user_id: int):
    # 감정(GOOD, NORMAL, BAD) 별 상태(BUSY, FREE)에서의 총 사용 시간
    # 어제, 1주일, 2주일, 1개월
    today = date.today()
    periods = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week_1": (today - timedelta(days=7), today - timedelta(days=1)),
        "week_2": (today - timedelta(days=14), today - timedelta(days=1)),
        "month_1": (today - timedelta(days=30), today - timedelta(days=1)),
    }

    response = {}

    for label, (start_date, end_date) in periods.items():
        rows = (
            db.query(
                DailySummary.dominant_emotion,
                DailySummary.status,
                func.sum(DailySummary.total_usage_ms).label("total_ms")
            )
            .filter(
                DailySummary.user_id == user_id,
                DailySummary.date >= start_date,
                DailySummary.date <= end_date,
                DailySummary.dominant_emotion.isnot(None),
                DailySummary.status.isnot(None)
            )
            .group_by(DailySummary.dominant_emotion, DailySummary.status)
            .all()
        )
        
        # Initialize structure: {EMOTION: {STATUS: ms}}
        period_result = {
            "GOOD": {"BUSY": 0, "FREE": 0},
            "NORMAL": {"BUSY": 0, "FREE": 0},
            "BAD": {"BUSY": 0, "FREE": 0},
        }
        
        for r in rows:
            emo = r.dominant_emotion
            st = r.status
            ms = int(r.total_ms or 0)
            
            if emo in period_result:
                # status가 BUSY, FREE 외에 다른 것이 올 수도 있으므로 setdefault 사용 or 단순 할당
                if st not in period_result[emo]:
                    period_result[emo][st] = 0
                period_result[emo][st] += ms
                
        response[label] = period_result

    return response
