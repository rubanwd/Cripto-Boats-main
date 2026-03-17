import os

API_KEY = os.environ.get("API_KEY", "R35w15sVKVGr8oPEdL")
API_SECRET = os.environ.get("API_SECRET", "iZIXKQHvCx8iaskUSRV4bDXhaDzdmqhAkkxq")

exchange_config = {
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True,
        'recvWindow': 60000,
    },
    'timeout': 30000,
}

# Попробуем без переопределения urls, только флаг test
# Для демо-аккаунта
exchange_config['options']['brokerId'] = 'demo'
exchange_config['urls'] = {
    'api': {
        'public': 'https://api-demo.bybit.com',
        'private': 'https://api-demo.bybit.com',
    }
}
exchange_config['headers'] = {
    'Referer': 'https://bybit.com'
}

# Количество итераций для пропуска пары после закрытия позиции по противоположному сигналу
ITERATIONS_TO_SKIP_AFTER_CLOSE = 2

# Таймфрейм для работы бота (в минутах)
TIMEFRAME = '15'

# Количество свечей (time_steps) для анализа истории нейросетями
TIME_STEPS = 1000

# Настройки Take Profit и Stop Loss (в процентах от маржи/депозита в сделке)
# Так как у нас плечо 10x, то изменение цены на 1% дает 10% PnL
TAKE_PROFIT_PCT = 0.30  # Закрывать в плюс при 30% прибыли (ROI)
STOP_LOSS_PCT = 0.15    # Закрывать в минус при 15% убытка (ROI)


