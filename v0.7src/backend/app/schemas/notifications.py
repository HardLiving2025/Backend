from pydantic import BaseModel
from datetime import datetime
from typing import List


class NotificationItem(BaseModel):
    noti_id: int
    message_type: str
    sent_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
