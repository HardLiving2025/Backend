
# ai_module/utils.py

import os

# PAM (Picture Affect Meter) Mapping
# 1-4: High Arousal, Negative (Angry, Stressed) -> BAD
# 5-8: High Arousal, Positive (Excited, Happy) -> GOOD
# 9-12: Low Arousal, Negative (Sad, Bored) -> BAD
# 13-16: Low Arousal, Positive (Calm, Relaxed) -> GOOD
PAM_MAPPING = {
    1: 'BAD', 2: 'BAD', 3: 'BAD', 4: 'BAD',
    5: 'GOOD', 6: 'GOOD', 7: 'GOOD', 8: 'GOOD',
    9: 'BAD', 10: 'BAD', 11: 'BAD', 12: 'BAD',
    13: 'GOOD', 14: 'GOOD', 15: 'GOOD', 16: 'GOOD'
}

EMOTION_TO_INT = {
    'GOOD': 1,
    'NORMAL': 0, # Placeholder if needed
    'BAD': -1
}

# Calendar Status Mapping
STATUS_TO_INT = {
    'FREE': 0,
    'BUSY': 1
}

# App Categories (Fallback if not found in DB or constants)
# Extending from backend/app/utils/constants.py if possible, but defining here for standalone safety.
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
    # OTHER (Defaults handled in logic)
    "com.spotify.music": "OTHER",
    "com.netflix.mediaclient": "OTHER",
    "com.android.chrome": "OTHER",
    "com.google.android.gm": "OTHER",
}

# Paths
DATASET_ROOT = "/home/t25335/dataset"
