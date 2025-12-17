# 모델 구현 파일 
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import GRU, Dense, Dropout
from tensorflow.keras.optimizers import Adam

def build_model(input_shape):
    # 출력: (24, 3) 
    # 인코더-디코더 아키텍처
    
    from tensorflow.keras.layers import TimeDistributed, Reshape, RepeatVector
    
    model = Sequential([
        # [Encoder] 
        # 입력된 시계열 정보를 압축 (24 steps -> 1 vector)
        # GRU 모델 채택하여 시계열 데이터를 학습할 것임. 
        GRU(64, input_shape=input_shape, return_sequences=False),
        Dropout(0.3),
        
        # [Bridge]
        # 압축된 정보를 24시간 분량으로 복제하여 Decoder에 전달
        RepeatVector(24),
        
        # [Decoder]
        # 복제된 정보를 바탕으로 24시간의 흐름을 다시 생성
        GRU(64, return_sequences=True),
        Dropout(0.3),
        
        # [Output]
        # TimeDistributed를 사용하여 매 시간(24 steps)마다 독립적으로 3개 카테고리 예측
        # 각 시간대별로 3개 값 출력 (Output Shape: 24, 3)
        TimeDistributed(Dense(3, activation='sigmoid'))
    ])
    
    # 손실 함수: MSE (3개 카테고리의 0~1 값 회귀 예측)
    model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
    return model
