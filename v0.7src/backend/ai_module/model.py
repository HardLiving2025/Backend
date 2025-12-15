
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import GRU, Dense, Dropout
from tensorflow.keras.optimizers import Adam

def build_model(input_shape):
    # Output: 24 (Next 24 hours Normalized Usage)
    # Activation: Sigmoid (Because normalized 0-1)
    
    model = Sequential([
        GRU(64, input_shape=input_shape, return_sequences=True),
        Dropout(0.2),
        GRU(64, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        # Output layer: 24 features (hours)
        Dense(24, activation='sigmoid')
    ])
    
    # Loss: MSE (Regression on 0-1 values)
    # Binary Crossentropy could work too, but MSE is more standard for "amount".
    model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
    return model
