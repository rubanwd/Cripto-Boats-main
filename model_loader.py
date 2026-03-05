import os
import logging
import joblib
from models import FocalLoss

# Устанавливаем переменную окружения для отключения предупреждений TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

def load_lstm_model_func():
    if os.path.exists('lstm_trading_model.h5') and os.path.exists('lstm_scaler.pkl'):
        try:
            # Импортируем tensorflow и keras только внутри функции, чтобы избежать проблем с глобальным стейтом
            import tensorflow as tf
            from tensorflow.keras.models import load_model
            
            # Для Keras 3+ нужно явно регистрировать все инициализаторы
            try:
                from keras.src.initializers import Orthogonal, GlorotUniform, Zeros
            except ImportError:
                # Fallback для старых версий
                from tensorflow.keras.initializers import Orthogonal, GlorotUniform, Zeros

            custom_objects = {
                'FocalLoss': FocalLoss,
                'Orthogonal': Orthogonal,
                'GlorotUniform': GlorotUniform,
                'Zeros': Zeros
            }
            
            # В Keras 3 format='h5' нужно указывать явно, если файл h5
            model = load_model('lstm_trading_model.h5', 
                             custom_objects=custom_objects,
                             compile=False)
            scaler = joblib.load('lstm_scaler.pkl')
            return model, scaler
        except Exception as e:
            logging.error(f"Error loading LSTM model or scaler: {e}")
            return None, None
    logging.warning("LSTM model or scaler files not found.")
    return None, None

def load_random_forest_model_func():
    if os.path.exists('random_forest_model.pkl') and os.path.exists('random_forest_scaler.pkl'):
        try:
            model = joblib.load('random_forest_model.pkl')
            scaler = joblib.load('random_forest_scaler.pkl')
            return model, scaler
        except Exception as e:
            logging.error(f"Error loading Random Forest model or scaler: {e}")
            return None, None
    logging.warning("Random Forest model or scaler files not found.")
    return None, None
