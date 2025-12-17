# backend/app/cron/generate_daily_summary.py

import os
import sys
from datetime import date, timedelta

# backend/ 경로 상위까지 자동 등록
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.database import SessionLocal
from app.models.usage_raw import AppUsageRaw
from app.models.daily_summary import DailySummary


def generate_daily_summary():
    db = SessionLocal()

    try:
        today = date.today()
        target = today - timedelta(days=1)

        rows = db.query(AppUsageRaw).filter(
            AppUsageRaw.usage_date == target
        ).all()

        if not rows:
            print(f"[SUMMARY] No data for {target}")
            return

        total_ms = sum(r.duration_ms for r in rows)

        summary = DailySummary(
            summary_date=target,
            total_usage_ms=total_ms
        )
        db.add(summary)
        db.commit()

        print(f"[SUMMARY] Summary created for {target} ({total_ms} ms)")

    except Exception as e:
        print("[ERROR]", e)

    finally:
        db.close()


if __name__ == "__main__":
    generate_daily_summary()
