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

