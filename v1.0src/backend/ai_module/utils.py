
# ai_module/utils.py

import os

# PAM (사진 감정 측정) 매핑 , StudentLife 셋에서 불러온 것임. 우리의 DB 에서  GOOD,BAD로 매칭 가능함. 
# 1-4: 높은 각성, 부정적 (화남, 스트레스) -> BAD
# 5-8: 높은 각성, 긍정적 (흥분, 행복) -> GOOD
# 9-12: 낮은 각성, 부정적 (슬픔, 지루함) -> BAD
# 13-16: 낮은 각성, 긍정적 (차분함, 편안함) -> GOOD
PAM_MAPPING = {
    1: 'BAD', 2: 'BAD', 3: 'BAD', 4: 'BAD',
    5: 'GOOD', 6: 'GOOD', 7: 'GOOD', 8: 'GOOD',
    9: 'BAD', 10: 'BAD', 11: 'BAD', 12: 'BAD',
    13: 'GOOD', 14: 'GOOD', 15: 'GOOD', 16: 'GOOD'
}

EMOTION_TO_INT = {
    'GOOD': 1,
    'NORMAL': 0, # 필요 시 사용될 예비 값
    'BAD': -1
}

# 캘린더 상태 매핑
STATUS_TO_INT = {
    'FREE': 0,
    'BUSY': 1
}

# 앱 카테고리 (DB나 상수에 없을 경우를 위한 대비책)
# 가능하면 backend/app/utils/constants.py를 확장해서 쓰되, 안전을 위해 독립적으로 정의
CATEGORY_MAP = {
    # SNS
    "com.kakao.talk": "SNS",
    "com.instagram.android": "SNS",
    "com.twitter.android": "SNS",
    "com.discord": "SNS",
    "com.google.android.youtube": "SNS",
    "com.everytime.v2": "SNS",
    "com.facebook.katana": "SNS",
    # GAME
    "com.geode.launcher": "GAME",
    "gg.dak.bser": "GAME",
    "com.robtopx.geometryjump": "GAME",
    "com.riotgames.league.teamfighttactics": "GAME",
    "com.supercell.clashofclans": "GAME",
    "com.king.candycrushsaga": "GAME",
    "com.rovio.angrybirds": "GAME",
    # OTHER (기타는 로직에서 기본값으로 처리)
    "com.spotify.music": "OTHER",
    "com.netflix.mediaclient": "OTHER",
    "com.android.chrome": "OTHER",
    "com.google.android.gm": "OTHER",
}

# 경로 설정
DATASET_ROOT = "/home/t25335/dataset"
