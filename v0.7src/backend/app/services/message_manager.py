class MessageManager:

    DEFAULT_MESSAGES = {
        "DANGER": {
            "title": "주의가 필요해요",
            "body": "현재 상태에서는 과몰입 위험이 높아요. 잠시 쉬었다가 다시 시작해보세요."
        },
        "CAUTION": {
            "title": "조금 주의하세요",
            "body": "지금은 사용량이 조금 높은 편이에요."
        },
        "SAFE": {
            "title": "좋아요!",
            "body": "건강한 스마트폰 사용 패턴을 유지하고 있어요."
        }
    }

    @staticmethod
    def get_message(level: str, emotion: str, status: str):
        # 지금은 단순한 기본 메시지만 사용
        return MessageManager.DEFAULT_MESSAGES[level]
