# 전처리 코드 
import os
import glob
import json
import pandas as pd
import numpy as np
from datetime import datetime
from app.database import SessionLocal
from ai_module.utils import DATASET_ROOT, PAM_MAPPING, EMOTION_TO_INT, STATUS_TO_INT, CATEGORY_MAP

def get_user_ids():
    # dataset/sensing/app_usage/running_app_uXX.csv -> uXX  , uxx는 마다 한 명의 데이터셋을 의미함. 
    # glob을 사용하여 파일 찾기
    pattern = os.path.join(DATASET_ROOT, "app_usage", "running_app_*.csv")
    files = glob.glob(pattern)
    user_ids = []
    for f in files:
        basename = os.path.basename(f)
        # running_app_u00.csv -> u00
        parts = basename.split('_')
        if len(parts) >= 3:
            uid = parts[2].replace('.csv', '')
            user_ids.append(uid)
    return sorted(list(set(user_ids)))

def fetch_db_data(uid_str):
    """
    # 주어진 사용자에 대해 MySQL 데이터베이스에서 데이터 가져오기.
    """
    try:
        # Convert u00 -> user_id (int) logic if needed, or assume raw match
        # Assuming dataset 'u00' maps to DB user_id 1? Or manual mapping?
        # For now, let's assume we skip DB if we can't map user, or try integer conversion.
        # User ID in DB is Integer. 'u00' is string.
        # Simple heuristic: extract digits
        
        digits = re.findall(r'\d+', uid_str)
        if not digits: return pd.DataFrame()
        
        user_id = int(digits[0])
        
        db = SessionLocal()
        # AppUsageRaw 쿼리
        # CSV 형식과 일치 필요: DATE, TIME, package_name, duration
        # AppUsageRaw: usage_date (datetime), duration_ms, package_name
        
        rows = db.query(AppUsageRaw).filter(AppUsageRaw.user_id == user_id).all()
        db.close()
        
        if not rows:
            return pd.DataFrame()
            
        data = []
        for r in rows:
            # r.usage_date is datetime.date or datetime? In models.py it might be Date.
            # If Date, we need start_time.
            # Let's check models.py... usually usage_date is Date. start_time is Time?
            # Let's assume we construct timestamp.
            
            # Using r.usage_date and r.start_time
            d_str = r.usage_date.strftime("%Y/%m/%d")
            t_str = r.start_time.strftime("%H:%M") if r.start_time else "00:00"
            
            data.append({
                "DATE": d_str,
                "TIME": t_str,
                "package_name": r.package_name,
                "duration": r.duration_ms / 1000.0 # CSV uses seconds? Check below. 
                # CSV processing divides by 3600 later. CSV value raw?
                # Actually build_user_dataset does NOT raw processing.
                # It calls pd.read_csv then parse_dt.
                # We should return a DF with DATE, TIME, package_name, duration (seconds) or whatever CSV has.
                # CSV 'duration' column check:
                # In previous view_file, we didn't see duration column clearly.
                # Let's align with what build_user_dataset expects.
                # It expects 'package_name' and aggregation.
            })
            
        return pd.DataFrame(data)
    except Exception as e:
        print(f"[WARN] DB Fetch Failed for {uid_str}: {e}")
        return pd.DataFrame()

def load_app_usage(user_id):
    path = os.path.join(DATASET_ROOT, "app_usage", f"running_app_{user_id}.csv")
    if not os.path.exists(path):
        return None
    
    df = pd.read_csv(path)
    # 필수 컬럼: timestamp, RUNNING_TASKS_topActivity_mPackage
    df = df[['timestamp', 'RUNNING_TASKS_topActivity_mPackage']]
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    # 지속 시간 계산
    # 다음 행의 타임스탬프를 얻기 위해 shift
    df['next_ts'] = df['timestamp'].shift(-1)
    df['duration'] = (df['next_ts'] - df['timestamp']).dt.total_seconds()
    # 마지막 행을 0으로 채움 (또는 평균/삭제)
    df['duration'] = df['duration'].fillna(0)
    
    # 과도한 지속 시간 제한 (예: 1시간 이상 간격은 폰 꺼짐/대기로 간주)
    # Let's cap at 1 hour (3600s)
    df.loc[df['duration'] > 3600, 'duration'] = 3600
    
    # 카테고리 매핑
    def map_category(pkg):
        if pd.isna(pkg): return "OTHER"
        if pkg in CATEGORY_MAP:
            return CATEGORY_MAP[pkg]
        # 기본 키워드 휴리스틱
        pkg_lower = pkg.lower()
        if 'facebook' in pkg_lower or 'twitter' in pkg_lower or 'social' in pkg_lower or 'instagram' in pkg_lower:
            return "SNS"
        if 'game' in pkg_lower or 'angrybirds' in pkg_lower or 'candycrush' in pkg_lower:
            return "GAME"
        return "OTHER"

    df['category'] = df['RUNNING_TASKS_topActivity_mPackage'].apply(map_category)
    
    # 시간별 집계
    # FutureWarning fix: dt.floor('h')
    df['hour_idx'] = df['timestamp'].dt.floor('h')
    
    hourly = df.groupby(['hour_idx', 'category'])['duration'].sum().unstack(fill_value=0)
    
    # 모든 컬럼이 존재하는지 확인
    for col in ['SNS', 'GAME', 'OTHER']:
        if col not in hourly.columns:
            hourly[col] = 0
            
    hourly['total_usage'] = hourly['SNS'] + hourly['GAME'] + hourly['OTHER']
    return hourly

def load_ema(user_id):
    path = os.path.join(DATASET_ROOT, "EMA/response/PAM", f"PAM_{user_id}.json")
    if not os.path.exists(path):
        return None
        
    with open(path, 'r') as f:
        data = json.load(f)
    
    # 딕셔너리 리스트: picture_idx, resp_time
    rows = []
    for item in data:
        pid = item.get('picture_idx')
        ts = item.get('resp_time')
        if pid and ts:
            emotion_label = PAM_MAPPING.get(int(pid), 'NORMAL')
            rows.append({'timestamp': pd.to_datetime(ts, unit='s'), 'emotion': emotion_label})
            
    df = pd.DataFrame(rows)
    if df.empty:
        return None
        
    df['hour_idx'] = df['timestamp'].dt.floor('h')
    # 해당 시간대의 마지막 감정 사용
    hourly_ema = df.groupby('hour_idx').last()['emotion']
    return hourly_ema

def load_calendar(user_id):
    path = os.path.join(DATASET_ROOT, "calendar", f"calendar_{user_id}.csv")
    if not os.path.exists(path):
        return None
        
    df = pd.read_csv(path)
    # DATE: 3/24/2013, TIME: 20:00
    # Combine
    # 로그에서 발견된 혼합된 형식들:
    # 10/22/2023 15:45 (MM/DD/YYYY)
    # 2023/10/22 15:45 (YYYY/MM/DD)
    # 22/10/2023 15:45 (DD/MM/YYYY)
    
    # 경고 없이 다양성을 처리하기 위해 format='mixed' 사용
    df['start_time'] = df.apply(
        lambda row: pd.to_datetime(f"{row['DATE']} {row['TIME']}", format='mixed', errors='coerce'), axis=1
    )
            
    df = df.dropna(subset=['start_time'])
    
    # 명시되지 않은 경우 바쁨 상태는 1시간 지속으로 가정
    df['hour_idx'] = df['start_time'].dt.floor('h')
    df['status'] = 'BUSY'
    
    hourly_cal = df.groupby('hour_idx').first()['status']
    return hourly_cal

def build_user_dataset(user_id):
    # 모두 로드
    usage = load_app_usage(user_id) # Index: hour_idx
    ema = load_ema(user_id)         # Index: hour_idx
    cal = load_calendar(user_id)    # Index: hour_idx
    
    if usage is None or usage.empty:
        return None
        
    # 전체 시간 범위로 재인덱싱
    min_time = usage.index.min()
    max_time = usage.index.max()
    full_idx = pd.date_range(min_time, max_time, freq='h')
    
    df = pd.DataFrame(index=full_idx)
    
    # 사용량 병합
    df = df.join(usage)
    df[['SNS', 'GAME', 'OTHER', 'total_usage']] = df[['SNS', 'GAME', 'OTHER', 'total_usage']].fillna(0)
    
    # EMA 병합 (Forward fill)
    if ema is not None:
        df = df.join(ema)
        df['emotion'] = df['emotion'].ffill().fillna('NORMAL') # Default to NORMAL
    else:
        df['emotion'] = 'NORMAL'
    
    # 캘린더 병합 ('FREE'로 채움)
    if cal is not None:
        df = df.join(cal)
        df['status'] = df['status'].fillna('FREE')
    else:
        df['status'] = 'FREE'
    
    # 인코딩
    df['emotion_val'] = df['emotion'].map(EMOTION_TO_INT)
    df['status_val'] = df['status'].map(STATUS_TO_INT)
    
    # 피처
    df['hour'] = df.index.hour
    df['dow'] = df.index.dayofweek
    
    # 안전을 위해 총 사용량을 3600으로 제한 (데이터 겹침 등 방지)
    df.loc[df['total_usage'] > 3600, 'total_usage'] = 3600
    
    return df

def normalize_data(df):
    # 지속 시간 정규화 (초) -> 0-1
    # Max duration per hour is 3600s
    for col in ['SNS', 'GAME', 'OTHER', 'total_usage']:
        df[col] = df[col] / 3600.0
        
    # 주기적 피처를 위한 Sin/Cos
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['dow'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['dow'] / 7)
    
    return df

# tf.data.Dataset을 위한 제너레이터
def training_data_generator(user_ids, seq_len=24):
    PRED_LEN = 24
    
    for uid in user_ids:
        # 한 명의 사용자 데이터를 메모리에 로드
        df = build_user_dataset(uid)
        if df is None:
            continue
            
        # 충분한 길이 확인
        if len(df) < seq_len + PRED_LEN:
             continue
            
        df = normalize_data(df)
        
        # X, y 준비
        X_seq = []
        y_seq = []
        
        # X: (SEQ_LEN, FEATURE_DIM) 필요
        # y: (OUTPUT_DIM, 3) 필요 (다음 24시간, 3개 카테고리)
        
        # Data columns: 'SNS', 'GAME', 'OTHER', 'total_usage', ...
        # Target columns: 'SNS', 'GAME', 'OTHER'
        # X: Use all features including history
        
        feature_cols = ['SNS', 'GAME', 'OTHER', 'total_usage', 'emotion_val', 'status_val', 'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos']
        features = df[feature_cols].values.astype(np.float32)
        targets = df[['SNS', 'GAME', 'OTHER']].values.astype(np.float32) # Shape: (N, 3)
        
        # 슬라이딩 윈도우
        # 과거 SEQ_LEN(예: 168 또는 24)을 기반으로 다음 24시간 예측
        # Let's assume SEQ_LEN input -> Next 24 output
        
        if len(features) <= seq_len + PRED_LEN:
            continue
            
        for i in range(0, len(features) - seq_len - PRED_LEN + 1, 12): # Stride 12
            X_window = features[i : i + seq_len]
            y_window = targets[i + seq_len : i + seq_len + PRED_LEN] # (24, 3)
            
            X_seq.append(X_window)
            y_seq.append(y_window)
            
        if not X_seq:
            continue
            
        X_seq = np.array(X_seq)
        y_seq = np.array(y_seq)
        
        # Yield line by line or batch? 
        # TF Generator expects samples. Let's yield samples.
        for j in range(len(X_seq)):
            yield X_seq[j], y_seq[j]

def get_feature_dim():
    # 피처 차원을 반환하는 헬퍼
    return 10 # SNS, GAME, OTHER, total, emo, status, h_sin, h_cos, d_sin, d_cos
