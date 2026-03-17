import json
import logging
import time
import asyncio
from typing import List
from pybit.unified_trading import HTTP
import pandas as pd

from config import API_KEY, API_SECRET, TIMEFRAME

async def fetch_markets(session):
    try:
        response = session.get_instruments_info(category="linear")
        markets = {item['symbol']: item for item in response['result']['list']}
        return markets
    except Exception as e:
        logging.error(f"Error fetching markets: {e}")
        return {}

async def get_top_symbols(session, symbols, top_n=120):
    try:
        response = session.get_tickers(category="linear")
        tickers = response['result']['list']
        # Filter tickers that are in our symbols list and sort by turnover24h
        valid_tickers = [t for t in tickers if t['symbol'] in symbols]
        valid_tickers.sort(key=lambda x: float(x.get('turnover24h', 0)), reverse=True)
        return [t['symbol'] for t in valid_tickers[:top_n]]
    except Exception as e:
        logging.error(f"Error fetching top symbols: {e}")
        return []

async def fetch_min_amounts(session, top_symbols, markets):
    min_amounts = {}
    for symbol in top_symbols:
        market = markets.get(symbol)
        if market and 'lotSizeFilter' in market and 'minOrderQty' in market['lotSizeFilter']:
            min_amounts[symbol] = float(market['lotSizeFilter']['minOrderQty'])
        else:
            min_amounts[symbol] = 1.0
    return min_amounts

async def get_data_async(session, symbol, timeframe=TIMEFRAME, limit=1000):
    try:
        # map timeframe to pybit format if needed (e.g., '15m' -> '15')
        tf = timeframe.replace('m', '')
        # Максимальный лимит Bybit для kline - 1000. Если нужно больше, нужна пагинация.
        # Пока оставим 1000, так как это максимум для одного запроса.
        response = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=tf,
            limit=min(limit, 1000)
        )
        
        lst = response.get("result", {}).get("list", [])
        if not lst:
            return None
            
        df = pd.DataFrame(lst, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df.set_index('timestamp', inplace=True)
        df = df.sort_index()
        return df
    except Exception as e:
        logging.error(f"Error fetching data for {symbol}: {e}")
        return None
