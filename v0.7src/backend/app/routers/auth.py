from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import GoogleAuthRequest, TokenResponse
from app.models.users import User
from app.utils.jwt import create_access_token

router = APIRouter()

# POST /auth/google
# 구글 로그인 처리
@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    google_id = payload.google_id

    # 1) 기존 유저인지 확인
    user = db.query(User).filter(User.google_id == google_id).first()

    # 2) 없으면 신규 생성
    if not user:
        user = User(
            google_id=google_id,
            nickname=payload.nickname or "User"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 3) JWT 발급
    access_token = create_access_token(
        data={"sub": str(user.user_id)}  # sub = user_id 저장
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.user_id,
        nickname=user.nickname
    )
