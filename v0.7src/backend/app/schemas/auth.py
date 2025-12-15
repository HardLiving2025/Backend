from pydantic import BaseModel
from typing import Optional

class GoogleAuthRequest(BaseModel):
    google_id: str
    nickname: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nickname: Optional[str]
