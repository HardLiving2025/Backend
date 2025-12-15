
import sys
import json
import os
import subprocess
import numpy as np
import pandas as pd
# Lazy Import: Do NOT import tensorflow here

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_module.utils import PAM_MAPPING, EMOTION_TO_INT, STATUS_TO_INT

MODEL_PATH = os.path.join(os.path.dirname(__file__), "saved_models", "risk_gru.keras")

def find_free_gpu():
    try:
        cmd = ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True)
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
        min_t, max_t = hourly.index.min(), hourly.index.max()
        full_idx = pd.date_range(min_t, max_t, freq='h')
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
        
    return data.reshape(1, SEQ_LEN, -1)

def run_prediction():
    # 1. GPU Auto Setup (Before TF Import)
    target_gpu = find_free_gpu()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(target_gpu)
    
    # 2. Lazy Import
    global tf
    import tensorflow as tf
    
    # Memory Growth
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
        X = process_input_data(input_data)
        
        # Metadata
        user_id = input_data.get('user_id', 0)
        analysis_date = input_data.get('analysis_date', 'Tomorrow')
        current_emotion = input_data.get('emotion', 'NORMAL')
        
        if X is None:
            print(json.dumps({"error": "Insufficient data"}))
            return
            
        if not os.path.exists(MODEL_PATH):
             print(json.dumps({"error": "Model not found"}))
             return
             
        model = tf.keras.models.load_model(MODEL_PATH)
        out = model.predict(X, verbose=0)
        
        hourly_preds = out[0].tolist() # 24 float values
        total_pred_secs = sum(hourly_preds) * 3600.0
        
        # --- 1. Risk Analysis ---
        THRESHOLD_SECS = 4 * 3600.0
        ratio = total_pred_secs / THRESHOLD_SECS
        if ratio <= 1.0:
            score_val = ratio * 0.7
        else:
            score_val = 0.7 + (ratio - 1.0) * 0.1
            if score_val > 1.0: score_val = 1.0
            
        risk_score_int = int(score_val * 100)
        risk_level = "HIGH" if score_val >= 0.7 else ("MODERATE" if score_val >= 0.4 else "LOW")
        
        # Determine Vulnerable Category from Input (Simple Sum)
        # X shape: (1, SEQ_LEN, 10). Indices 0:SNS, 1:GAME, 2:OTHER
        # We sum across sequence to see which one was dominant recently
        input_sums = np.sum(X[0, :, :3], axis=0) # [sum_sns, sum_game, sum_other]
        cats = ['SNS', 'GAME', 'OTHER']
        vuln_idx = np.argmax(input_sums)
        vulnerable_category = cats[vuln_idx]
        
        condition_msg = f"기분이 {current_emotion} 상태일 때" if current_emotion != "NORMAL" else "평소 상태일 때"
        risk_msg = f"{condition_msg} {vulnerable_category} 앱 과다 사용 위험이 있습니다." if risk_level == "HIGH" else "사용량이 양호할 것으로 예상됩니다."

        risk_analysis = {
            "level": risk_level,
            "score": risk_score_int,
            "vulnerable_category": vulnerable_category,
            "condition": current_emotion,
            "message": risk_msg
        }
        
        # --- 2. Usage Prediction (Peak Hour) ---
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
            "target_category": vulnerable_category, # Predicting the same dominant category for simplicity
            "probability_percent": round(max_val * 100, 1) # Normalized 0-1 to %
        }
        
        # --- 3. Pattern Detection (Simple Logic) ---
        # Detect Night Owl (High usage 22:00 - 04:00)
        # Indices: 22, 23, 0, 1, 2, 3
        night_indices = [22, 23, 0, 1, 2, 3]
        night_sum = sum([hourly_preds[i] for i in night_indices])
        is_night_owl = night_sum > (total_pred_secs / 3600.0 * 0.4) # > 40% of usage at night
        
        pattern_detection = {
            "detected": is_night_owl,
            "pattern_code": "PATTERN_NIGHT_OWL" if is_night_owl else "NONE",
            "alert_message": "심야 시간대 사용 집중 감지" if is_night_owl else ""
        }
        
        # --- Final Construction ---
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
        # 3. Robust Cleanup
        if 'tf' in locals() or 'tf' in globals():
            try:
                tf.keras.backend.clear_session()
            except:
                pass

if __name__ == "__main__":
    run_prediction()
