from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.moods import MoodCreateRequest, MoodCreateResponse
from app.models.emotion_status_logs import EmotionStatusLog
from app.utils.security import get_current_user  # ← JWT 적용!

router = APIRouter()


@router.post("")
def create_mood(
    payload: MoodCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)   # ← JWT 적용!
):
    mood = EmotionStatusLog(
        user_id=user.user_id,
        emotion=payload.emotion,
        status=payload.status
    )

    db.add(mood)
    db.commit()
    db.refresh(mood)

    return MoodCreateResponse(
        emotion_id=mood.emotion_id,
        emotion=mood.emotion,
        status=mood.status,
        created_at=mood.created_at.isoformat()
    )
