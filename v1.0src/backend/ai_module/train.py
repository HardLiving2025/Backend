
import os
import sys
import argparse
import signal
import subprocess
import numpy as np
import gc
# 지연 로딩: 여기서 tensorflow를 import하지 않음. 
# 원활한 서버 condition 유지를 위해서 안전한 방식으로 import 할 것임. 

# 부모 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_module.preprocessing import get_user_ids, training_data_generator, get_feature_dim
# TF를 import하므로 아직 build_model을 import하지 마세요

MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "saved_models", "risk_gru.keras")

def find_free_gpu():
    """
    nvidia-smi를 실행하여 메모리 사용량이 가장 적은(비어있는) GPU 번호를 자동으로 찾습니다.
    """
    try:
        cmd = ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            print(">>> [WARN] nvidia-smi failed. Defaulting to GPU 0.", flush=True)
            return 0
            
        lines = result.stdout.strip().split('\n')
        gpu_memory = []
        for line in lines:
            if not line: continue
            parts = line.split(',')
            idx = int(parts[0].strip())
            mem_used = int(parts[1].strip())
            gpu_memory.append((idx, mem_used))
            
        if not gpu_memory:
            return 0
            
        # Sort by memory used (ASC)
        gpu_memory.sort(key=lambda x: x[1])
        best_gpu = gpu_memory[0][0]
        free_mem = gpu_memory[0][1]
        
        print(f">>> [AUTO-GPU] Best GPU found: #{best_gpu} (Used: {free_mem} MB)", flush=True)
        return best_gpu
        
    except Exception as e:
        print(f">>> [WARN] Auto-GPU selection failed: {e}. Defaulting to GPU 0.", flush=True)
        return 0

def handle_shutdown(signum, frame):
    print(f"\n\n>>> [SHUTDOWN] Signal {signum} received. Cleaning up...", flush=True)
    # 지연 로딩된 import 정리 확인
    if 'tf' in sys.modules:
        try:
            import tensorflow as tf
            tf.keras.backend.clear_session()
            print(">>> [SHUTDOWN] TensorFlow session cleared.", flush=True)
        except:
            pass
    gc.collect()
    sys.exit(0)

def train_model(args): # 각 Step 을 print 하도록 하여 진행상황 확인 가능하게 함. 
    # 1. TensorFlow import 전에 GPU 환경 변수 설정
    target_gpu = args.gpu if args.gpu is not None else find_free_gpu()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(target_gpu)
    print(f">>> [SETUP] CUDA_VISIBLE_DEVICES set to: {target_gpu}", flush=True)
    
    # 2. 이제 TensorFlow import (지연 로딩)
    print(">>> [Step 1] Initializing TensorFlow...", flush=True)
    global tf
    import tensorflow as tf
    from ai_module.model import build_model
    
    # 메모리 증가 설정
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f">>> [SETUP] GPU Memory Growth Enabled for {len(gpus)} device(s).", flush=True)
        except RuntimeError as e:
            print(f">>> [SETUP] GPU Growth Error: {e}", flush=True)
    
    # 신호 등록
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGHUP, handle_shutdown)
    
    try:
        print(">>> [Step 2] Loading User IDs... (Preparing Generator)", flush=True)
        uids = get_user_ids()
        print(f"    Found {len(uids)} users.", flush=True)
        
        if not uids:
            print(">>> [Error] No users found. Exiting.", flush=True)
            return

        SEQ_LEN = 24
        FEATURE_DIM = get_feature_dim()
        # 출력 차원 = 24 * 3 (모델에서 24, 3으로 재구조화)
        # 제너레이터의 타겟 형태는 (24, 3)
        
        print(">>> [Step 3] Building Data Pipeline...", flush=True)
        
        output_signature = (
            tf.TensorSpec(shape=(SEQ_LEN, FEATURE_DIM), dtype=tf.float32),
            tf.TensorSpec(shape=(24, 3), dtype=tf.float32)
        )
        
        split_idx = int(len(uids) * 0.8)
        train_uids = uids[:split_idx]
        val_uids = uids[split_idx:]
        
        print(f"    Train Users: {len(train_uids)}, Valid Users: {len(val_uids)}", flush=True)
        
        BATCH_SIZE = 64
        BUFFER_SIZE = 5000 
        
        train_ds = tf.data.Dataset.from_generator(
            lambda: training_data_generator(train_uids, seq_len=SEQ_LEN),
            output_signature=output_signature
        ).shuffle(BUFFER_SIZE).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
        
        val_ds = tf.data.Dataset.from_generator(
            lambda: training_data_generator(val_uids, seq_len=SEQ_LEN),
            output_signature=output_signature
        ).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

        print(">>> [Step 4] Building Model...", flush=True)
        model = build_model((SEQ_LEN, FEATURE_DIM))
        # model.summary()
        
        from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

        print(">>> [Step 5] Starting Training (with Early Stopping & LR Scheduler)...", flush=True)
        EPOCHS = 50
        
        callbacks = [
            EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),
            ModelCheckpoint(MODEL_SAVE_PATH, monitor='val_loss', save_best_only=True, verbose=1),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001, verbose=1)
        ]
        
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=EPOCHS,
            callbacks=callbacks,
            verbose=1
        )
        
        print(">>> [Step 6] Saving Model...", flush=True)
        if not os.path.exists(os.path.dirname(MODEL_SAVE_PATH)):
            os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
            
        model.save(MODEL_SAVE_PATH)
        print(f"    Saved to: {MODEL_SAVE_PATH}", flush=True)
        print(">>> [Success] Training Complete.", flush=True)
        
    except Exception as e:
        print(f"\n>>> [ERROR] Exception occurred: {e}", flush=True)
        raise e
        
    finally:
        print("\n>>> [Cleanup] Clearing Session...", flush=True)
        if 'tf' in locals() or 'tf' in globals():
            try:
                tf.keras.backend.clear_session()
            except:
                pass
        gc.collect()
        print(">>> [Cleanup] Done.", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-Scalable AI Training with Lazy Loading")
    parser.add_argument("--gpu", type=int, default=None, help="Manually specify GPU ID (optional)")
    args = parser.parse_args()
    
    train_model(args)
