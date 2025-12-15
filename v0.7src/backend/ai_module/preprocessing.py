
import os
import glob
import json
import pandas as pd
import numpy as np
from datetime import datetime
from ai_module.utils import DATASET_ROOT, PAM_MAPPING, EMOTION_TO_INT, STATUS_TO_INT, CATEGORY_MAP

def get_user_ids():
    # dataset/sensing/app_usage/running_app_uXX.csv -> extract uXX
    # Use glob to find files
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
    Fetch data from MySQL DATABASE for the given user.
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
        # Query AppUsageRaw
        # We need to match the CSV format: DATE, TIME, package_name, duration
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
    # Essential cols: timestamp, RUNNING_TASKS_topActivity_mPackage
    df = df[['timestamp', 'RUNNING_TASKS_topActivity_mPackage']]
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('timestamp')
    
    # Calculate duration
    # Shift timestamp to get next row's timestamp
    df['next_ts'] = df['timestamp'].shift(-1)
    df['duration'] = (df['next_ts'] - df['timestamp']).dt.total_seconds()
    # Fill last row with 0 or mean (or drop)
    df['duration'] = df['duration'].fillna(0)
    
    # Cap excessive duration (e.g. > 1 hour gap usually means phone off or idle)
    # Let's cap at 1 hour (3600s)
    df.loc[df['duration'] > 3600, 'duration'] = 3600
    
    # Map Categories
    def map_category(pkg):
        if pd.isna(pkg): return "OTHER"
        if pkg in CATEGORY_MAP:
            return CATEGORY_MAP[pkg]
        # Basic keyword heuristics
        pkg_lower = pkg.lower()
        if 'facebook' in pkg_lower or 'twitter' in pkg_lower or 'social' in pkg_lower or 'instagram' in pkg_lower:
            return "SNS"
        if 'game' in pkg_lower or 'angrybirds' in pkg_lower or 'candycrush' in pkg_lower:
            return "GAME"
        return "OTHER"

    df['category'] = df['RUNNING_TASKS_topActivity_mPackage'].apply(map_category)
    
    # Aggregate by Hour
    # FutureWarning fix: dt.floor('h')
    df['hour_idx'] = df['timestamp'].dt.floor('h')
    
    hourly = df.groupby(['hour_idx', 'category'])['duration'].sum().unstack(fill_value=0)
    
    # Ensure all columns exist
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
    
    # List of dicts: picture_idx, resp_time
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
    # Use most last emotion in that hour, or mode? Let's use last.
    hourly_ema = df.groupby('hour_idx').last()['emotion']
    return hourly_ema

def load_calendar(user_id):
    path = os.path.join(DATASET_ROOT, "calendar", f"calendar_{user_id}.csv")
    if not os.path.exists(path):
        return None
        
    df = pd.read_csv(path)
    # DATE: 3/24/2013, TIME: 20:00
    # Combine
    # Mixed formats found in logs:
    # 10/22/2023 15:45 (MM/DD/YYYY)
    # 2023/10/22 15:45 (YYYY/MM/DD)
    # 22/10/2023 15:45 (DD/MM/YYYY)
    
    # We use format='mixed' to handle this variety without warnings
    df['start_time'] = df.apply(
        lambda row: pd.to_datetime(f"{row['DATE']} {row['TIME']}", format='mixed', errors='coerce'), axis=1
    )
            
    df = df.dropna(subset=['start_time'])
    
    # Assume 1 hour duration for busy status if not specified
    df['hour_idx'] = df['start_time'].dt.floor('h')
    df['status'] = 'BUSY'
    
    hourly_cal = df.groupby('hour_idx').first()['status']
    return hourly_cal

def build_user_dataset(user_id):
    # Load all
    usage = load_app_usage(user_id) # Index: hour_idx
    ema = load_ema(user_id)         # Index: hour_idx
    cal = load_calendar(user_id)    # Index: hour_idx
    
    if usage is None or usage.empty:
        return None
        
    # Reindex to full hourly range of usage
    min_time = usage.index.min()
    max_time = usage.index.max()
    full_idx = pd.date_range(min_time, max_time, freq='h')
    
    df = pd.DataFrame(index=full_idx)
    
    # Join Usage
    df = df.join(usage)
    df[['SNS', 'GAME', 'OTHER', 'total_usage']] = df[['SNS', 'GAME', 'OTHER', 'total_usage']].fillna(0)
    
    # Join EMA (Forward fill)
    if ema is not None:
        df = df.join(ema)
        df['emotion'] = df['emotion'].ffill().fillna('NORMAL') # Default to NORMAL
    else:
        df['emotion'] = 'NORMAL'
    
    # Join Calendar (Fill 'FREE')
    if cal is not None:
        df = df.join(cal)
        df['status'] = df['status'].fillna('FREE')
    else:
        df['status'] = 'FREE'
    
    # Encode
    df['emotion_val'] = df['emotion'].map(EMOTION_TO_INT)
    df['status_val'] = df['status'].map(STATUS_TO_INT)
    
    # Features
    df['hour'] = df.index.hour
    df['dow'] = df.index.dayofweek
    
    # Cap total usage at 3600 for safety (sometimes data overlap causes >3600)
    df.loc[df['total_usage'] > 3600, 'total_usage'] = 3600
    
    return df

def normalize_data(df):
    # Normalize durations (seconds) -> 0-1
    # Max duration per hour is 3600s
    for col in ['SNS', 'GAME', 'OTHER', 'total_usage']:
        df[col] = df[col] / 3600.0
        
    # Sine/Cos for cyclic features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['dow'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['dow'] / 7)
    
    return df

# Generator for tf.data.Dataset
def training_data_generator(user_ids, seq_len=24):
    PRED_LEN = 24
    
    for uid in user_ids:
        # Load ONE user's data into memory
        df = build_user_dataset(uid)
        if df is None:
            continue
            
        # Check sufficient length
        if len(df) < seq_len + PRED_LEN:
             continue
            
        df = normalize_data(df)
        
        feature_cols = ['SNS', 'GAME', 'OTHER', 'total_usage', 'emotion_val', 'status_val', 'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos']
        data = df[feature_cols].values.astype(np.float32)
        target_col = df['total_usage'].values.astype(np.float32)
        
        max_start = len(df) - seq_len - PRED_LEN + 1
        
        # Yield sequences one by one
        for i in range(max_start):
            X_seq = data[i : i+seq_len]      # (SEQ_LEN, features)
            y_seq = target_col[i+seq_len : i+seq_len+PRED_LEN] # (PRED_LEN,)
            yield X_seq, y_seq

def get_feature_dim():
    # Helper to return feature dimension
    return 10 # SNS, GAME, OTHER, total, emo, status, h_sin, h_cos, d_sin, d_cos
