import sys
import codecs
import io
# Устанавливаем кодировку UTF-8 по умолчанию для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import tensorflow as tf
import asyncio
import ccxt.async_support as ccxt_async
import logging
import time
from config import exchange_config, ITERATIONS_TO_SKIP_AFTER_CLOSE

async def get_time_difference():
    try:
        temp_exchange = ccxt_async.bybit()
        server_time = await temp_exchange.fetch_time()
        local_time = int(time.time() * 1000)
        await temp_exchange.close()
        return server_time - local_time
    except Exception as e:
        logging.error(f"Failed to fetch server time: {e}")
        return 0
from logging_config import *
from fetcher import fetch_markets, get_top_symbols, fetch_min_amounts, get_data_async
from model_loader import load_lstm_model_func, load_random_forest_model_func
from trainer import train_lstm_model, train_random_forest_model_wrapper
from predictor import predict_signal_ensemble, get_separate_signals
from trade_manager import get_real_balance, manage_position
from collections import deque
from keras_tuner import RandomSearch # ВАЖНО: нужно добавить импорт RandomSearch

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    from pybit.unified_trading import HTTP
    
    # Инициализация нативного клиента pybit
    session = HTTP(
        testnet=False, # Demo Trading runs on mainnet URLs with demo flag
        demo=True, # Включаем демо режим
        api_key=exchange_config['apiKey'],
        api_secret=exchange_config['secret'],
    )
    
    try:
        markets = await fetch_markets(session)
        excluded_symbols = ['UNFIUSDT', 'TIAUSDT']
        all_symbols = [
            symbol for symbol, market in markets.items()
            if market.get('quoteCoin') == 'USDT' and market.get('status') == 'Trading' and symbol not in excluded_symbols
        ]
        top_symbols = await get_top_symbols(session, all_symbols)
        top_symbols = [
            symbol for symbol in top_symbols if symbol not in excluded_symbols
        ]
        min_amounts = await fetch_min_amounts(session, top_symbols, markets)
        lstm_model, lstm_scaler = await asyncio.to_thread(load_lstm_model_func)
        rf_model, rf_scaler = await asyncio.to_thread(load_random_forest_model_func)
        if not lstm_model or not rf_model:
            lstm_model, lstm_scaler = await train_lstm_model(session, top_symbols)
            if lstm_model and lstm_scaler:
                rf_model, rf_scaler = await train_random_forest_model_wrapper(top_symbols, session)
            else:
                logging.critical("Failed to load or train models. Exiting program.")
                return
        trades_deque = deque(maxlen=1000)

        skipped_symbols = {}

        async def trade_signals():
            while True:
                # 1. Update skipped symbols
                symbols_to_remove = []
                for sym in skipped_symbols:
                    skipped_symbols[sym] -= 1
                    if skipped_symbols[sym] <= 0:
                        symbols_to_remove.append(sym)
                for sym in symbols_to_remove:
                    del skipped_symbols[sym]

                # 2. Check open positions and close if opposite signal
                try:
                    positions_response = session.get_positions(category="linear", settleCoin="USDT")
                    open_positions = [p for p in positions_response.get('result', {}).get('list', []) if float(p.get('size', '0')) > 0]
                    
                    for pos in open_positions:
                        symbol = pos['symbol']
                        side = pos['side']
                        size = pos['size']
                        
                        try:
                            df = await get_data_async(session, symbol, timeframe='15')
                            if df is not None:
                                lstm_signal, rf_signal = get_separate_signals(df, lstm_model, lstm_scaler, rf_model, rf_scaler)
                                if lstm_signal is not None and rf_signal is not None:
                                    should_close = False
                                    if side == 'Buy' and (lstm_signal == 0 or rf_signal == 0):
                                        should_close = True
                                    elif side == 'Sell' and (lstm_signal == 1 or rf_signal == 1):
                                        should_close = True
                                    
                                    if should_close:
                                        close_side = 'Sell' if side == 'Buy' else 'Buy'
                                        logging.info(f"Closing position for {symbol} due to opposite prediction. Side: {side}, LSTM: {lstm_signal}, RF: {rf_signal}")
                                        try:
                                            session.place_order(
                                                category="linear",
                                                symbol=symbol,
                                                side=close_side,
                                                orderType="Market",
                                                qty=str(size),
                                                reduceOnly=True
                                            )
                                            skipped_symbols[symbol] = ITERATIONS_TO_SKIP_AFTER_CLOSE
                                            logging.info(f"Successfully closed {symbol}. Skipping for {ITERATIONS_TO_SKIP_AFTER_CLOSE} iterations.")
                                        except Exception as e:
                                            logging.error(f"Error closing position for {symbol}: {e}")
                        except Exception as e:
                            logging.error(f"Error processing open position for {symbol}: {e}")
                except Exception as e:
                    logging.error(f"Error fetching open positions: {e}")

                usdt_balance = await get_real_balance(session)
                if usdt_balance is None:
                    logging.warning("Failed to get USDT balance. Retrying in 5 seconds.")
                    await asyncio.sleep(5)
                    continue
                for symbol in top_symbols:
                    if symbol in skipped_symbols:
                        continue
                    try:
                        df = await get_data_async(session, symbol, timeframe='15')
                        if df is not None:
                            signal = predict_signal_ensemble(df, lstm_model, lstm_scaler,
                                                             rf_model, rf_scaler)
                            if signal is not None:
                                await manage_position(session, symbol, signal,
                                                      usdt_balance, min_amounts, lstm_model,
                                                      lstm_scaler, rf_model, rf_scaler)
                    except Exception as e:
                        logging.error(f"Error processing signal for {symbol}: {e}")
                await asyncio.sleep(300)

        await asyncio.gather(trade_signals())
    except KeyboardInterrupt:
        logging.info("Interrupt signal received. Shutting down...")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        logging.info("Program terminated")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
