from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import delete
from datetime import datetime, date, timedelta, time

from app.database import get_db
from app.schemas.usage import UsageDaySchema, UsageBatchResponse
from app.models.app_usage_raw import AppUsageRaw
from typing import List
from app.utils.security import get_current_user
from app.utils.constants import CATEGORY_MAP

router = APIRouter()


@router.post("/batch", response_model=UsageBatchResponse)
def upload_usage_batch(
    payload: List[UsageDaySchema],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    user_id = current_user.user_id
    
    # 1. Parse all data and prepare for processing
    # To check duplication efficiently, we group by (date, slot)
    # But for "Delete-Insert" strategy, we can just collect unique (date, slot) keys to delete first.
    
    slots_to_delete = set()
    new_records = []
    
    for slot_data in payload:
        usage_date_str = slot_data.usage_date
        time_slot_str = slot_data.time_slot
        
        try:
            # Parse usage_date and time_slot
            date_obj = date.fromisoformat(usage_date_str)
            h, m = map(int, time_slot_str.split(':'))
            
            # Calculate slot_index (0~47)
            slot_index = (h * 60 + m) // 30
            
            # Calculate start_time and end_time
            start_dt = datetime.combine(date_obj, time(hour=h, minute=m))
            end_dt = start_dt + timedelta(minutes=30)
            
            # Add to deletion target set: (user_id, date, slot_index)
            # user_id is fixed for this request
            slots_to_delete.add((date_obj, slot_index))
            
            # Prepare new records
            for pkg_name, duration in slot_data.package_data.items():
                if duration <= 0:
                    continue

                mapped_category = CATEGORY_MAP.get(pkg_name, "OTHER")
                
                new_records.append(AppUsageRaw(
                    user_id=user_id,
                    usage_date=date_obj,
                    package_name=pkg_name,
                    category=mapped_category,
                    duration_ms=duration,
                    slot_index=slot_index,
                    start_time=start_dt,
                    end_time=end_dt
                ))
                
        except ValueError as e:
            print(f"[Error] Invalid date/time format: {usage_date_str} {time_slot_str} - {e}")
            continue

    # 2. Delete existing records for the target slots
    if slots_to_delete:
        for (d_obj, s_idx) in slots_to_delete:
            db.query(AppUsageRaw).filter(
                AppUsageRaw.user_id == user_id,
                AppUsageRaw.usage_date == d_obj,
                AppUsageRaw.slot_index == s_idx
            ).delete()
        
    # 3. Bulk Insert
    if new_records:
        db.bulk_save_objects(new_records)
        
    db.commit()

    return UsageBatchResponse(
        saved_count=len(new_records),
        message="Batch upload successful"
    )
