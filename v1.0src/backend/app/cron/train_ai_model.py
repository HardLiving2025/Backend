# backend/app/cron/train_ai_model.py

"""
AI 모델 주간 학습 자동 실행 스크립트
- 학습용 데이터 조회 (AppUsageRaw + Emotion Logs)
- ai/train_data.json 으로 저장
- 향후 PyTorch 학습 코드 연동 가능
"""

import os
import sys
import json
from datetime import date, timedelta

# backend/ 상위경로 등록
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.database import SessionLocal
from app.models.usage_raw import AppUsageRaw
from app.models.emotion_log import EmotionStatusLog


# AI 데이터 저장 위치
AI_DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "ai")
AI_TRAIN_FILE = os.path.join(AI_DATA_DIR, "train_data.json")


def collect_training_data(db):
    # 최근 30일 데이터를 학습용으로 수집
    end = date.today()
    start = end - timedelta(days=30)

    usage_rows = db.query(AppUsageRaw).filter(
        AppUsageRaw.usage_date.between(start, end)
    ).order_by(AppUsageRaw.usage_date.asc()).all()

    emotion_rows = db.query(EmotionStatusLog).filter(
        EmotionStatusLog.created_at.between(start, end)
    ).order_by(EmotionStatusLog.created_at.asc()).all()

    usage_data = [
        {
            "user_id": r.user_id,
            "date": str(r.usage_date),
            "category": r.category,
            "duration_ms": r.duration_ms,
        }
        for r in usage_rows
    ]

    emotion_data = [
        {
            "user_id": r.user_id,
            "emotion": r.emotion,
            "status": r.status,
            "timestamp": str(r.created_at),
        }
        for r in emotion_rows
    ]

    return {
        "start_date": str(start),
        "end_date": str(end),
        "usage": usage_data,
        "emotions": emotion_data,
    }


def train_ai_model():
    db = SessionLocal()

    try:
        # 1) 학습 데이터 수집
        data = collect_training_data(db)

        # ai/train_data.json 저장
        os.makedirs(AI_DATA_DIR, exist_ok=True)
        with open(AI_TRAIN_FILE, "w") as f:
            json.dump(data, f, indent=4)

        print(f"[TRAIN] Training data saved to {AI_TRAIN_FILE}")
        print(f"[TRAIN] (Dummy) Model training step completed.")
