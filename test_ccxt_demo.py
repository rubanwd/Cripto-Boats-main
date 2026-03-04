import ccxt
import time
import requests

exchange = ccxt.bybit({
    'apiKey': 'eSLaJxUMfxEATayRbE',
    'secret': 'v28DdPI6oa2rPQXrB5z4ibkp3QuN4ENbC733',
    'options': {
        'recvWindow': 60000,
    }
})
exchange.urls['api'] = {
    'public': 'https://api-demo.bybit.com',
    'private': 'https://api-demo.bybit.com',
}

server_time = requests.get('https://api-demo.bybit.com/v5/market/time').json()['time']
local_time = int(time.time() * 1000)
exchange.options['timeDifference'] = server_time - local_time

try:
    print(exchange.fetch_balance())
except Exception as e:
    print("Error:", e)
