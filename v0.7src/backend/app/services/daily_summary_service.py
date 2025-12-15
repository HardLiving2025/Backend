from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.app_usage_raw import AppUsageRaw
from app.models.daily_summary import DailySummary
from app.models.emotion_status_logs import EmotionStatusLog
from app.utils.constants import CATEGORY_MAP


class DailySummaryService:

    # 1. 하루치 raw usage → summary로 변환
    @staticmethod
    def generate_summary_for_date(user_id: int, target_date: date, db: Session):

        # 1) 이미 존재하는지 확인
        existing = db.query(DailySummary).filter(
            DailySummary.user_id == user_id,
            DailySummary.date == target_date
        ).first()

        if existing:
            return existing  # 이미 생성됨

        print("[DEBUG] daily summary job started", flush=True)

        # CATEGORY_MAP moved to class level

        # 2) raw data 조회
        raw_rows = db.query(AppUsageRaw).filter(
            AppUsageRaw.user_id == user_id,
            AppUsageRaw.usage_date == target_date
        ).all()

        if not raw_rows:
            # 사용 기록 없음 -> 아무것도 생성하지 않거나 빈 레코드 1개?
            # 요청사항: "값이 없으면 컬럼 생성하지 않도록" -> 레코드 생성 안 함
            return True

        # 3) 감정/상태 로직 (Day: 08-18, Night: 18-08)
        # Day Window: target_date 08:00 ~ 18:00
        day_start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=8)
        day_end = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=18)
        
        # Night Window: target_date 18:00 ~ next_day 08:00
        night_start = day_end
        night_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=8)

        # Day Log
        day_log = db.query(EmotionStatusLog).filter(
            EmotionStatusLog.user_id == user_id,
            EmotionStatusLog.created_at >= day_start,
            EmotionStatusLog.created_at < day_end
        ).order_by(EmotionStatusLog.created_at.desc()).first()

        # Night Log (Includes pre-dawn? User said 18-08. We check this window)
        night_log = db.query(EmotionStatusLog).filter(
            EmotionStatusLog.user_id == user_id,
            EmotionStatusLog.created_at >= night_start,
            EmotionStatusLog.created_at < night_end
        ).order_by(EmotionStatusLog.created_at.desc()).first()

        
        # --- [New Logic] 알림 무시 횟수 및 코멘트 생성 ---
        from app.models.notification_logs import NotificationLog
        
        # 야간 알림 체크 (전날 18:00 ~ 오늘 09:00? or 오늘 18:00 ~ 내일 09:00?)
        # 기존 로직: 전날 18:00 ~ 알림 집계는 "전날의 데이터"를 기반으로 하므로,
        # DailySummary가 'target_date' 에 대한 것이면, target_date의 밤을 의미하는지 확인 필요.
        # User Context from Step 47: "전날 데이터 입력... 8일에... 밤 데이터... 9일 새벽..."
        # So for Date=Target, if Target is "Yesterday", we want (Target 18:00 ~ Target+1 09:00).
        # We will keep consistent with previous implementation for notification window.
        noti_night_start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=18)
        noti_night_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=9)

        ignored_count = db.query(NotificationLog).filter(
            NotificationLog.user_id == user_id,
            NotificationLog.is_read == False,
            NotificationLog.risk_level.in_(["CAUTION", "DANGER"]),
            NotificationLog.sent_at >= noti_night_start,
            NotificationLog.sent_at < noti_night_end
        ).count()

        # 총 사용 시간 계산
        total_usage_sum = sum(row.duration_ms for row in raw_rows)
        hours = total_usage_sum // (1000 * 60 * 60)
        minutes = (total_usage_sum % (1000 * 60 * 60)) // (1000 * 60)
        usage_str = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
        comment = f"최근 {ignored_count}번 경고를 무시하셨어요. 어제 핸드폰 총 사용량은 {usage_str}입니다."


        # 4) 30분 슬롯(0~47) 초기화
        # 하지만 "값이 없으면 생성하지 않도록" -> Dict로 관리하고 데이터 있는 곳만 저장
        slots = {} # key: slot_index, val: {sns, game, other}

        for row in raw_rows:
            # raw data는 현재 1일 1행(duration sum)으로 들어오고 있음 (Step 195).
            # 따라서 시간 정보(start/end)가 없으므로 정확한 30분 슬롯 배정이 불가능함.
            # 그러나 User Request 3번: "time_slot이 00:00일 때 값이 있으면... 04:00일 때 값이 없으면..."
            # 이는 raw data가 다시 '시간대별'로 들어오거나, start_time/end_time이 있다고 가정하는 것임.
            # 현재 AppUsageRaw 스키마는 start_time/end_time이 주석처리되어 있음.
            # 하지만 usage_month.json에는 "time_slot"이 있음.
            # 로직상, AppUsageRaw에 'start_time'이 없으면 슬롯 배분이 불가능.
            # 일단 전체 시간을 '0번 슬롯' 또는 '적절한 슬롯'에 넣어야 하는데...
            # ! CRITICAL: user reverted schema changes for start_time.
            # But the user logic demands "time_slot".
            # The ONLY way is if AppUsageRaw HAS time info.
            # Currently it DOES NOT. It only has "usage_date".
            # I will assume for now we aggregate EVERYTHING into Slot 0 (since we can't distinguish) 
            # OR I distributes it evenly?
            # WAIT. If keys are Time Slots in usage_month.json, the User might expect us to USE that.
            # But usage.py aggregates it all into one day! (Step 195 applied aggregation).
            # So duplicate packages are merged and time info LOST.
            # CONFLICT: usage.py aggregates and loses time info -> daily_summary cannot recover time slots.
            # I must assume the user might have UN-DONE the aggregation or expects me to fix it?
            # Actually, looking at the request, the user seems to imply sparse slots.
            # Since I cannot recover time from aggregated data, I will dump everything into Slot 0 (or a default) 
            # OR, I must use 'created_at' if available? No.
            
            # Since I cannot change usage.py right now (not requested), I have to work with what I have.
            # I will put everything in Slot 0 for now as a fallback, BUT apply the Category Map.
            
            pkg = row.package_name
            # Force Category Map
            cat_key = CATEGORY_MAP.get(pkg, "OTHER")
            
            # For now, assign to Slot 0 (Time 00:00) because we lost granularity.
            # If the user wants granular slots, they need to NOT aggregate in usage.py.
            # I will proceed with logic that supports specific slots IF we had them, 
            # but currently default to 0.
            
            target_slot = 0 # Default
            
            if target_slot not in slots:
                slots[target_slot] = {"sns": 0, "game": 0, "other": 0}
            
            if cat_key == "SNS":
                slots[target_slot]["sns"] += row.duration_ms
            elif cat_key == "GAME":
                slots[target_slot]["game"] += row.duration_ms
            else:
                slots[target_slot]["other"] += row.duration_ms

        # 6) DB 저장 (데이터가 있는 슬롯만 iterating)
        # Note: Since we only put in Slot 0, only Slot 0 will be saved.
        # If we had time info, this loop would handle the sparse requirement naturally.
        
        has_comment_saved = False

        for idx, usage in slots.items():
            start_dt = datetime.combine(target_date, datetime.min.time()) + timedelta(minutes=30*idx)
            end_dt = start_dt + timedelta(minutes=30)
            
            # Emotion Selection based on Time Window
            # 08:00 <= Time < 18:00 -> Day
            hour = start_dt.hour
            chosen_log = None
            if 8 <= hour < 18:
                chosen_log = day_log
            else:
                chosen_log = night_log
                
            dom_emotion = chosen_log.emotion if chosen_log else None
            dom_status = chosen_log.status if chosen_log else None

            # Comment only on first saved slot
            row_comment = comment if not has_comment_saved else None
            if row_comment:
                has_comment_saved = True

            total_ms = usage["sns"] + usage["game"] + usage["other"]
            if total_ms == 0:
                continue

            summary = DailySummary(
                user_id=user_id,
                date=target_date,
                slot_index=idx,
                start_time=start_dt,
                end_time=end_dt,
                sns_ms=usage["sns"],
                game_ms=usage["game"],
                other_ms=usage["other"],
                total_usage_ms=total_ms,
                dominant_emotion=dom_emotion,
                status=dom_status,
                comment=row_comment,
                created_at=datetime.now()
            )
            db.add(summary)

        db.commit()
        return True

    # 3. 프론트엔드 데이터 처리 (NEW)
    @staticmethod
    def process_frontend_data(user_id: int, data: list, db: Session):
        """
        data: List[DailyUsageInput] (Schema object list)
        """
        # 날짜별로 그룹화가 필요할 수도 있지만, 입력 데이터가 특정 날짜들에 대한 것이라 가정하고 처리
        # 효율성을 위해 날짜별로 기존 데이터를 조회하는 것이 좋음.
        
        # 1) 들어온 데이터 순회
        # data는 Pydantic 모델 리스트라고 가정
        
        processed_count = 0
        
        for item in data:
            usage_date = item.usage_date
            time_slot_str = item.time_slot # "HH:MM"
            packages = item.package # dict
            
            # 시간 파싱
            h, m = map(int, time_slot_str.split(':'))
            # 30분 단위 슬롯 인덱스 계산 (0~47)
            # 00:00 -> 0, 00:30 -> 1, 01:00 -> 2 ...
            slot_idx = (h * 60 + m) // 30
            
            # 시작/종료 시간 계산
            start_dt = datetime.combine(usage_date, datetime.min.time()) + timedelta(minutes=30*slot_idx)
            end_dt = start_dt + timedelta(minutes=30)
            
            # 카테고리별 합산
            sns_ms = 0
            game_ms = 0
            other_ms = 0
            
            for pkg_name, duration in packages.items():
                cat = CATEGORY_MAP.get(pkg_name, "OTHER")
                if cat == "SNS":
                    sns_ms += duration
                elif cat == "GAME":
                    game_ms += duration
                else:
                    other_ms += duration
                    
            total_ms = sns_ms + game_ms + other_ms
            
            if total_ms == 0:
                continue

            # DB 조회 (해당 슬롯이 이미 있는지)
            # 반복문 내 쿼리는 좋지 않으나, 하루 max 48번 * 날짜 수 이므로 일단 진행
            summary = db.query(DailySummary).filter(
                DailySummary.user_id == user_id,
                DailySummary.date == usage_date,
                DailySummary.slot_index == slot_idx
            ).first()
            
            if not summary:
                summary = DailySummary(
                    user_id=user_id,
                    date=usage_date,
                    slot_index=slot_idx,
                    start_time=start_dt,
                    end_time=end_dt,
                    sns_ms=sns_ms,
                    game_ms=game_ms,
                    other_ms=other_ms,
                    total_usage_ms=total_ms,
                    created_at=datetime.now()
                )
                db.add(summary)
            else:
                # 이미 있으면 업데이트 (덮어쓰기 or 누적? 여기선 덮어쓰기 로직이 적절해 보임)
                summary.sns_ms = sns_ms
                summary.game_ms = game_ms
                summary.other_ms = other_ms
                summary.total_usage_ms = total_ms
                # 감정/상태/코멘트는 여기서 건드리지 않음 (필요시 추가 로직)
                
            processed_count += 1
            
        db.commit()
        return processed_count

    # 2. 하루 전(어제) 데이터를 자동 생성
    @staticmethod
    def generate_yesterday(user_id: int, db: Session):
        yesterday = date.today() - timedelta(days=1)
        return DailySummaryService.generate_summary_for_date(user_id, yesterday, db)
