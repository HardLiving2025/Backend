from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
from google.oauth2 import id_token
from google.auth.transport import requests

from app.database import get_db
from app.schemas.auth import GoogleAuthRequest, GoogleAuthDevRequest, TokenResponse
from app.models.users import User
from app.utils.jwt import create_access_token

router = APIRouter()

# 구글 로그인 처리 (ID Token 검증 방식)
@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    # 1) Google ID Token 검증
    try:
        GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Server configuration error: GOOGLE_CLIENT_ID not set")
        
        # Google 서버에 토큰 검증 요청
        idinfo = id_token.verify_oauth2_token(
            payload.id_token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # 검증된 사용자 정보 추출
        google_user_id = idinfo['sub']  # 구글 고유 사용자 ID
        email = idinfo.get('email', '')
        name = idinfo.get('name', 'User')
        
    except ValueError as e:
        # 토큰이 유효하지 않거나 만료됨
        raise HTTPException(status_code=401, detail=f"Invalid ID token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token verification failed: {str(e)}")

    # 2) 기존 유저인지 확인
    user = db.query(User).filter(User.google_id == google_user_id).first()

    # 3) 없으면 신규 생성, 있으면 토큰 업데이트
    if not user:
        user = User(
            google_id=google_user_id,
            nickname=name,
            fcm_token=payload.fcm_token
        )
        db.add(user)
    else:
        # 기존 유저면 FCM 토큰 업데이트 (변경되었을 수 있음)
        if payload.fcm_token:
            user.fcm_token = payload.fcm_token
            
    db.commit()
    db.refresh(user)

    # 4) JWT 발급
    access_token = create_access_token(
        data={"sub": str(user.user_id)}
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.user_id,
        nickname=user.nickname
    )

# ⚠️ 개발 환경에서만 사용
@router.post("/google/dev", response_model=TokenResponse)
def google_login_dev(
    payload: GoogleAuthDevRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.google_id == payload.google_id).first()

    if not user:
        user = User(
            google_id=payload.google_id,
            nickname=payload.nickname,
            fcm_token=payload.fcm_token
        )
        db.add(user)
    else:
        if payload.fcm_token:
            user.fcm_token = payload.fcm_token
            
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        data={"sub": str(user.user_id)}
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.user_id,
        nickname=user.nickname
    )
