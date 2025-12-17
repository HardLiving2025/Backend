from pydantic import BaseModel
from datetime import datetime
from typing import List


class NotificationItem(BaseModel):
    noti_id: int
    message_type: str
    message_body: str
    sent_at: datetime


class NotificationRecentResponse(BaseModel):
    recent_notifications: List[NotificationItem] # Recent 3


class NotificationMessageResponse(BaseModel):
    title: str
    body: str
    risk_level: str
