import tensorflow as tf
import logging
import numpy as np
from data_utils import add_technical_indicators
from config import TIME_STEPS

def get_separate_signals(df, lstm_model, lstm_scaler, rf_model, rf_scaler, time_steps=TIME_STEPS):
    try:
        df = add_technical_indicators(df)
        data = df[[
            'open', 'high', 'low', 'close', 'volume', 'rsi', 'ema20', 'macd',
            'macd_signal', 'bollinger_hband', 'bollinger_lband', 'stoch', 'vwap',
            'atr', 'ichimoku_a', 'ichimoku_b', 'ichimoku_base_line',
            'ichimoku_conversion_line'
        ]].values
        data_scaled = lstm_scaler.transform(data)
        if len(data_scaled) < time_steps:
            logging.warning("Insufficient data for signal prediction")
            return None, None
        X_input_lstm = data_scaled[-time_steps:]
        X_input_lstm = np.expand_dims(X_input_lstm, axis=0)
        lstm_pred = lstm_model.predict(X_input_lstm, verbose=0)[0][0]
        
        # Смягчаем пороги для сигналов, чтобы поощрить открытие шортов.
        # Так как данные сбалансированы 50/50, выход модели должен быть около 0.5.
        # > 0.52 = Long, < 0.48 = Short
        lstm_signal = 1 if lstm_pred > 0.52 else (0 if lstm_pred < 0.48 else -1)
        
        X_input_rf = data_scaled[-time_steps:].flatten().reshape(1, -1)
        X_input_rf_scaled = rf_scaler.transform(X_input_rf)
        rf_pred = int(rf_model.predict(X_input_rf_scaled)[0])
        return lstm_signal, rf_pred
    except Exception as e:
        logging.error(f"Error in separate signal prediction: {e}")
        return None, None

def predict_signal_ensemble(df,
                            lstm_model,
                            lstm_scaler,
                            rf_model,
                            rf_scaler,
                            time_steps=TIME_STEPS):
    try:
        df = add_technical_indicators(df)
        data = df[[
            'open', 'high', 'low', 'close', 'volume', 'rsi', 'ema20', 'macd',
            'macd_signal', 'bollinger_hband', 'bollinger_lband', 'stoch', 'vwap',
            'atr', 'ichimoku_a', 'ichimoku_b', 'ichimoku_base_line',
            'ichimoku_conversion_line'
        ]].values
        data_scaled = lstm_scaler.transform(data)
        if len(data_scaled) < time_steps:
            logging.warning("Insufficient data for signal prediction")
            return None
        X_input_lstm = data_scaled[-time_steps:]
        X_input_lstm = np.expand_dims(X_input_lstm, axis=0)
        lstm_pred = lstm_model.predict(X_input_lstm, verbose=0)[0][0]
        
        # Смягчаем пороги для сигналов, чтобы поощрить открытие шортов.
        # Так как данные сбалансированы 50/50, выход модели должен быть около 0.5.
        # > 0.52 = Long, < 0.48 = Short
        lstm_signal = 1 if lstm_pred > 0.52 else (0 if lstm_pred < 0.48 else -1) # Добавлена зона неопределенности
        
        X_input_rf = data_scaled[-time_steps:].flatten().reshape(1, -1)
        X_input_rf_scaled = rf_scaler.transform(X_input_rf)
        rf_pred = int(rf_model.predict(X_input_rf_scaled)[0])
        
        # Строгая логика входа:
        # 1 = Long (Обе модели уверены в росте)
        # 0 = Short (Обе модели уверены в падении)
        # None = Неопределенность (модели не согласны)
        if lstm_signal == 1 and rf_pred == 1:
            return 1
        elif lstm_signal == 0 and rf_pred == 0:
            return 0
        else:
            return None
            
    except Exception as e:
        logging.error(f"Error in signal prediction: {e}")
        return None
