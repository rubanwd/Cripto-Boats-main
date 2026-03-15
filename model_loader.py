import os
import logging
import joblib
from models import FocalLoss

# Устанавливаем переменную окружения для отключения предупреждений TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Добавляем хак для Keras 3 для совместимости с инициализаторами из старых версий
import keras
if hasattr(keras, 'initializers'):
    keras.initializers.Orthogonal = keras.initializers.Orthogonal
    keras.initializers.GlorotUniform = keras.initializers.GlorotUniform
    keras.initializers.Zeros = keras.initializers.Zeros

def load_lstm_model_func():
    if os.path.exists('lstm_trading_model.h5') and os.path.exists('lstm_scaler.pkl'):
        try:
            from tensorflow.keras.models import load_model
            
            # Добавлено: игнорируем аргументы, которые могут вызывать ошибку при загрузке
            model = load_model('lstm_trading_model.h5', 
                             custom_objects={'FocalLoss': FocalLoss},
                             compile=False)
            
            scaler = joblib.load('lstm_scaler.pkl')
            return model, scaler
        except Exception as e:
            logging.error(f"Error loading LSTM model or scaler: {e}")
            # Если не удалось загрузить, удаляем битые файлы, чтобы они пересоздались
            try:
                os.remove('lstm_trading_model.h5')
                os.remove('lstm_scaler.pkl')
                logging.info("Deleted corrupted LSTM model files.")
            except:
                pass
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
            # Если не удалось загрузить, удаляем битые файлы, чтобы они пересоздались
            try:
                os.remove('random_forest_model.pkl')
                os.remove('random_forest_scaler.pkl')
                logging.info("Deleted corrupted Random Forest model files.")
            except:
                pass
            return None, None
    logging.warning("Random Forest model or scaler files not found.")
    return None, None
