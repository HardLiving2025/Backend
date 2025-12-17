from pydantic import BaseModel
from typing import Optional

class GoogleAuthRequest(BaseModel):
    id_token: str  # Google ID Token (구글 SDK에서 발급받은 토큰)
    fcm_token: Optional[str] = None

class GoogleAuthDevRequest(BaseModel):
    # 개발/테스트 환경용 간소화된 구글 로그인 요청
    google_id: str
    nickname: str
    fcm_token: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nickname: Optional[str]
