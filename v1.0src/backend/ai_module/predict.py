
import sys
import json
import os
import subprocess
import numpy as np
import pandas as pd
import signal
import atexit
import gc
# 지연 로딩: 여기서 tensorflow를 import하지않음. 
# 원활한 서버 condition 유지를 위해서 안전한 방식으로 import 할 것임. 

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_module.utils import PAM_MAPPING, EMOTION_TO_INT, STATUS_TO_INT

MODEL_PATH = os.path.join(os.path.dirname(__file__), "saved_models", "risk_gru.keras")

def find_free_gpu():
    try:
        cmd = ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0: return 0
        lines = result.stdout.strip().split('\n')
        gpu_memory = []
        for line in lines:
            if not line: continue
            parts = line.split(',')
            gpu_memory.append((int(parts[0]), int(parts[1])))
        if not gpu_memory: return 0
        gpu_memory.sort(key=lambda x: x[1])
        return gpu_memory[0][0]
    except:
        return 0

def process_input_data(json_data):
    seq_list = json_data.get('seq_data', [])
    current_emotion = json_data.get('emotion', 'NORMAL')
    current_status = json_data.get('status', 'FREE')
    
    if not seq_list: return None
        
    df = pd.DataFrame(seq_list)
    
    if 'start_time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['start_time'])
    elif 'usage_date' in df.columns:
        df['timestamp'] = pd.to_datetime(df['usage_date'])
    else:
        return None
        
    df['duration'] = df['duration_ms'] / 1000.0
    
    def map_cat(c):
        c = str(c).lower()
        if 'sns' in c: return 'SNS'
        if 'game' in c: return 'GAME'
        return 'OTHER'
    
    df['feat_cat'] = df['category'].apply(map_cat)
    df['hour_idx'] = df['timestamp'].dt.floor('h')
    hourly = df.groupby(['hour_idx', 'feat_cat'])['duration'].sum().unstack(fill_value=0)
    
    for c in ['SNS', 'GAME', 'OTHER']:
        if c not in hourly.columns: hourly[c] = 0
            
    hourly['total_usage'] = hourly['SNS'] + hourly['GAME'] + hourly['OTHER']
    
    if not hourly.empty:
        # [수정] 00:00 ~ 23:00으로 앵커링하여 희소 데이터가 이동하거나 압축되는 것을 방지.
        # 데이터는 대부분 하루치라고 가정 (호출자가 보장)
        # 첫 번째 타임스탬프에서 날짜를 가져옴
        anchor_date = hourly.index[0].date()
        start_dt = pd.Timestamp(anchor_date)
        end_dt = start_dt + pd.Timedelta(hours=23)
        
        full_idx = pd.date_range(start_dt, end_dt, freq='h')
        hourly = hourly.reindex(full_idx, fill_value=0)
    
    for col in ['SNS', 'GAME', 'OTHER', 'total_usage']:
        hourly[col] = hourly[col] / 3600.0
        
    hourly['hour'] = hourly.index.hour
    hourly['dow'] = hourly.index.dayofweek
    
    hourly['hour_sin'] = np.sin(2 * np.pi * hourly['hour'] / 24)
    hourly['hour_cos'] = np.cos(2 * np.pi * hourly['hour'] / 24)
    hourly['dow_sin'] = np.sin(2 * np.pi * hourly['dow'] / 7)
    hourly['dow_cos'] = np.cos(2 * np.pi * hourly['dow'] / 7)
    
    e_val = EMOTION_TO_INT.get(current_emotion, 0)
    s_val = STATUS_TO_INT.get(current_status, 0)
    
    hourly['emotion_val'] = e_val
    hourly['status_val'] = s_val
    
    feature_cols = ['SNS', 'GAME', 'OTHER', 'total_usage', 'emotion_val', 'status_val', 'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos']
    
    SEQ_LEN = 24
    data = hourly[feature_cols].values
    
    if len(data) < SEQ_LEN:
        pad_len = SEQ_LEN - len(data)
        pad = np.zeros((pad_len, len(feature_cols)))
        data = np.vstack([pad, data])
    else:
        data = data[-SEQ_LEN:]
        
    meta = {}
    
    if not df.empty:
        max_ts = df['timestamp'].max()
        min_ts = df['timestamp'].min()
        
        # 1. 분석 날짜: 
        # 00-24 및 08-08 패턴 모두 사용자는 "시작일 다음 날"을 직관적으로 기대함.
        # Case A (00-24): 시작 14일 00:00 -> 종료 14일 23:00. 타겟 = 15일. (시작 + 1일)
        # Case B (08-08): 시작 14일 08:00 -> 종료 15일 07:00. 타겟 = 15일. (시작 + 1일)
        # 구 로직 (Max + 1): 15일 + 1 = 16일 (Case B에서 틀림).
        # 신 로직 (Min + 1): 14일 + 1 = 15일 (둘 다 맞음).
        target_date = (min_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        meta['analysis_date'] = target_date
        
        # 2. 입력 유형 분류
        start_hour = min_ts.hour
        if 0 <= start_hour <= 2:
            meta['input_type'] = "TYPE_ALL_DAY" # 00-24
        elif 7 <= start_hour <= 9:
            meta['input_type'] = "TYPE_SHIFTED_DAY" # 08-08
        else:
            meta['input_type'] = "TYPE_IRREGULAR"
    else:
        meta['analysis_date'] = "Unknown"
        meta['input_type'] = "Unknown"

    meta['min_ts'] = str(df['timestamp'].min()) if not df.empty else ""
    meta['max_ts'] = str(df['timestamp'].max()) if not df.empty else ""

    return data.reshape(1, SEQ_LEN, -1), meta

def run_prediction():
    # 1. GPU 자동 설정 (TF Import 전)
    target_gpu = find_free_gpu()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(target_gpu)
    
    # 2. 지연 로딩
    global tf
    import tensorflow as tf
    
    # 메모리 증가
    gpus = tf.config.list_physical_devices('GPU')
    for gpu in gpus:
        try:
            tf.config.experimental.set_memory_growth(gpu, True)
        except: pass

    try:
        raw = sys.stdin.read()
        if not raw:
            print(json.dumps({"error": "Empty input"}))
            return
            
        input_data = json.loads(raw)
        X_result = process_input_data(input_data)
        
        if X_result is None:
            print(json.dumps({"error": "Insufficient data"}))
            return
            
        X, proc_meta = X_result
        
        # Metadata
        user_id = input_data.get('user_id', 0)
        # 동적으로 계산된 날짜 사용, 필요 시 입력값으로 대체 (동적 계산 선호)
        analysis_date = proc_meta.get('analysis_date', input_data.get('analysis_date', 'Tomorrow'))
        input_type = proc_meta.get('input_type', 'Unknown')
        
        current_emotion = input_data.get('emotion', 'NORMAL')
        
        if not os.path.exists(MODEL_PATH):
             print(json.dumps({"error": "Model not found"}))
             return
             
        model = tf.keras.models.load_model(MODEL_PATH)
        out = model.predict(X, verbose=0)
        
        # 출력 형태는 (1, 24, 3) -> [배치, 시간, 카테고리]
        # 카테고리: 0:SNS, 1:GAME, 2:OTHER
        pred_matrix = out[0] # Shape (24, 3)
        
        # 1. 시간별 총합 계산 (그래프 및 총 초 단위 사용량용)
        hourly_preds = np.sum(pred_matrix, axis=1).tolist() # Shape (24,)
        total_pred_secs = sum(hourly_preds) * 3600.0
        
        # 2. 취약 카테고리 결정 (예측 기반)
        # 모든 시간대에 대해 카테고리별 예측 합계
        cat_sums = np.sum(pred_matrix, axis=0) # Shape (3,) -> [Sum_SNS, Sum_GAME, Sum_OTHER]
        cats = ['SNS', 'GAME', 'OTHER']
        vuln_idx = np.argmax(cat_sums)
        vulnerable_category = cats[vuln_idx]
        
    # --- 1. 위험 분석 ---
        THRESHOLD_SECS = 6 * 3600.0 # 6 시간을 임계치로 측정함. 
        ratio = total_pred_secs / THRESHOLD_SECS
        if ratio <= 1.0:
            score_val = ratio * 0.7
        else:
            score_val = 0.7 + (ratio - 1.0) * 0.1
            if score_val > 1.0: score_val = 1.0
            
        risk_score_int = int(score_val * 100)
        risk_score_int = int(score_val * 100)
        risk_level = "DANGER" if score_val >= 0.7 else ("CAUTION" if score_val >= 0.4 else "SAFE")
        
        # 로컬라이제이션 매핑
        # 상태 매핑: BAD -> 기분이 좋지 않음, NORMAL -> 평범한, GOOD -> 기분이 좋음
        cond_map = {
            "BAD": "기분이 좋지 않음",
            "NORMAL": "평범한",
            "GOOD": "기분이 좋음"
        }
        # 카테고리 매핑: OTHER -> 기타, POST -> POST? (SNS/GAME/OTHER 로직 가정)
        # "SNS" -> "SNS", "GAME" -> "게임", "OTHER" -> "기타"
        cat_map = {
            "SNS": "SNS",
            "GAME": "게임",
            "OTHER": "기타"
        }
        
        kr_condition = cond_map.get(current_emotion, current_emotion)
        kr_category = cat_map.get(vulnerable_category, vulnerable_category)
        
        risk_msg = ""
        if risk_level == "DANGER":
            risk_msg = f"{kr_condition} 때 {kr_category} 앱 과다 사용 위험이 있습니다."
        elif risk_level == "CAUTION":
            risk_msg = f"{kr_condition} 때 {kr_category} 앱 사용에 주의가 필요합니다."
        else:
            risk_msg = "사용량이 양호할 것으로 예상됩니다."

        risk_analysis = {
            "level": risk_level,
            "score": risk_score_int,
            "vulnerable_category": vulnerable_category, 
            "condition": current_emotion,        
            "message": risk_msg
        }
        
        # --- 2. 사용량 예측 (피크 시간) ---
        max_idx = np.argmax(hourly_preds)
        max_val = hourly_preds[max_idx]
        
        start_h = int(max_idx)
        end_h = start_h + 1
        start_time_str = f"{start_h:02d}:00"
        end_time_str = f"{end_h:02d}:00" if end_h < 24 else "24:00"
        
        usage_prediction = {
            "has_prediction": True,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "target_category": vulnerable_category, 
            "probability_percent": round(max_val * 100, 1) # 0-1 정규화 값을 %로 변환
        }
        
        # --- 3. 패턴 감지 (단순 로직) ---
        # 아직 현 시스템에선 쓰이는 곳 없음, 하지만 추후 추가 가능. 
        # 올빼미족 감지 (22:00 - 04:00 높은 사용량)
        # 인덱스: 22, 23, 0, 1, 2, 3 # 늦은 시간을 정해놓음. 
        night_indices = [22, 23, 0, 1, 2, 3]
        night_sum = sum([hourly_preds[i] for i in night_indices])
        is_night_owl = night_sum > (total_pred_secs / 3600.0 * 0.4) # 야간 사용량이 40% 초과
        
        pattern_detection = {
            "detected": is_night_owl,
            "pattern_code": "PATTERN_NIGHT_OWL" if is_night_owl else "NONE",
            "alert_message": "심야 시간대 사용 집중 감지" if is_night_owl else ""
        }
        
        # --- 최종 결과 구성 ---
        result = {
            "user_id": user_id,
            "analysis_date": analysis_date,
            "risk_analysis": risk_analysis,
            "usage_prediction": usage_prediction,
            "pattern_detection": pattern_detection,
            # Keeping legacy fields for backward compatibility if needed, or removing
            # User requested "Return THIS format", assuming replacement.
            # But let's keep 'hourly_forecast' hidden or inside usage_prediction?
            # The prompt format didn't have hourly_forecast.
            # But frontend might need it for graph. I will add it as valid extra.
            "hourly_forecast": hourly_preds, 
            "total_predicted_seconds": total_pred_secs
        }
            
        print(json.dumps(result))
        
    except Exception as e:
        sys.stderr.write(str(e))
        # Error Response
        print(json.dumps({"error": str(e), "risk_analysis": {"level": "ERROR", "score": 0}}))
        
    finally:
        # 3. 강력한 정리 (atexit/signal이 처리하지만 명시적 호출도 안전함) , 좀비 프로세스 생성 방지를 위한. 
        cleanup()

def cleanup():
    """TensorFlow 세션을 명시적으로 정리하고 GC를 강제하여 VRAM 해제."""
    if 'tf' in globals():
        try:
            # TF Session Clear
            tf.keras.backend.clear_session()
        except: pass
        
    # Force Garbage Collection to release unreferenced GPU tensors
    gc.collect()

def signal_handler(signum, frame):
    """종료 신호 처리."""
    cleanup()
    sys.exit(0)

# 정리 핸들러 등록
atexit.register(cleanup)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    run_prediction()


