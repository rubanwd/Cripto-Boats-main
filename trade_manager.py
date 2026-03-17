import asyncio
import json
import logging
import time
import aiofiles
from fetcher import get_data_async
from predictor import predict_signal_ensemble
from config import TIMEFRAME, TAKE_PROFIT_PCT, STOP_LOSS_PCT

last_trade_time = {}
lock = asyncio.Lock()

async def get_real_balance(session):
    try:
        # accountType="UNIFIED" is typical for newer Bybit accounts
        response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        
        # Если API вернуло ошибку или пустой ответ
        if not response or 'result' not in response or not response['result']:
            logging.warning(f"Invalid or empty response from get_wallet_balance: {response}")
            return 0.0
            
        list_data = response.get('result', {}).get('list', [])
        if not list_data:
            logging.warning(f"No wallet list data returned from session.get_wallet_balance: {response}")
            
            # Попробуем запросить баланс обычного аккаунта деривативов, если UNIFIED не сработал
            try:
                response_contract = session.get_wallet_balance(accountType="CONTRACT", coin="USDT")
                list_data = response_contract.get('result', {}).get('list', [])
                if list_data:
                    logging.info(f"Successfully fetched balance from CONTRACT account instead of UNIFIED.")
                    account_data = list_data[0]
                else:
                    return 0.0
            except Exception as e2:
                logging.error(f"Failed to fetch CONTRACT balance as fallback: {e2}")
                return 0.0
        else:
            account_data = list_data[0]
            
        usdt_balance = 0.0
        
        # Для Unified Trading Account доступная маржа находится в totalAvailableBalance
        if 'totalAvailableBalance' in account_data and account_data['totalAvailableBalance']:
            usdt_balance = float(account_data['totalAvailableBalance'])
        elif 'totalEquity' in account_data and account_data['totalEquity']:
            usdt_balance = float(account_data['totalEquity'])
            
        # Если totalAvailableBalance по какой-то причине пуст (например, не Unified), ищем в монетах
        if usdt_balance == 0.0:
            for coin_data in account_data.get('coin', []):
                if coin_data['coin'] == 'USDT':
                    # В демо-счете availableToWithdraw может быть пустым, используем equity
                    balance_str = coin_data.get('equity', '0')
                    if not balance_str or float(balance_str) <= 0:  
                        balance_str = coin_data.get('walletBalance', '0')
                    if not balance_str or float(balance_str) <= 0:  
                        balance_str = coin_data.get('availableToWithdraw', '0')
                    if not balance_str:
                        balance_str = '0'
                    usdt_balance = float(balance_str)
                    break
                
        if usdt_balance <= 0:
            logging.warning(f"USDT balance is zero or negative ({usdt_balance}). Cannot trade. Raw account data: {account_data}")
            return 0.0
            
        return usdt_balance
    except Exception as e:
        logging.error(f"Error fetching real balance: {e}")
        return None

async def calculate_position_size(session,
                                  symbol,
                                  usdt_balance,
                                  risk_percentage=0.90, # Уменьшил до 90%
                                  min_amount=0):
    try:
        if usdt_balance <= 0:
            logging.warning(f"Cannot calculate position size. USDT balance is {usdt_balance}.")
            return None
            
        response = session.get_tickers(category="linear", symbol=symbol)
        current_price = float(response['result']['list'][0]['lastPrice'])
        
        if current_price is None or current_price <= 0:
            logging.error(f"Current price for {symbol} is missing")
            return None
            
        risk_amount = usdt_balance * risk_percentage
        position_size = risk_amount / current_price
        
        # Получаем размер шага из min_amount (это не совсем правильно, 
        # лучше использовать qtyStep, но пока возьмем его как базу)
        step_size = min_amount
        
        # Учитываем кредитное плечо при расчете размера позиции!
        # By default on new unified margin accounts it could be 10x
        leverage = 10 
        # position_size = position_size * leverage <- Убрал, потому что плечо не увеличивает размер контракта
        
        # Учитываем шаг размера позиции (qty_step)
        if step_size > 0:
            # Считаем количество знаков после запятой в шаге
            step_str = str(step_size)
            if '.' in step_str:
                precision = len(step_str.split('.')[1].rstrip('0'))
            else:
                precision = 0
            
            # Округляем до нужной точности, обрезая лишнее вниз (чтобы не превысить баланс)
            factor = 10 ** precision
            position_size = int(position_size * factor) / factor
            
            # Убеждаемся, что размер кратен шагу
            position_size = round(position_size / step_size) * step_size
            # Еще раз округляем из-за особенностей float
            position_size = round(position_size, precision)
        else:
            position_size = round(position_size, 3) 
        
        # Убеждаемся, что сделка больше минимальной стоимости ордера (Bybit требует минимум 5 USDT)
        min_order_value = 5.0
        if position_size * current_price < min_order_value:
            # Увеличиваем размер позиции до минимального, если риск позволяет
            # Или просто отменяем сделку, так как риск слишком мал для биржи
            if usdt_balance >= min_order_value / leverage:
                position_size = 6.0 / current_price # Делаем с запасом в 6$ чтобы точно прошло
                if step_size > 0:
                    position_size = round(position_size / step_size) * step_size
                    position_size = round(position_size, precision)
                else:
                    position_size = round(position_size + 0.001, 3)
            else:
                logging.warning(f"Insufficient balance to meet 5 USDT min order value for {symbol}")
                return None
                
    # 2. Недостаточно маржи на аккаунте - ErrCode: 110007 (ab not enough for new order)
    # Чтобы этого избежать, нужно использовать кросс-маржу или правильно рассчитывать стоимость с учетом плеча
        if position_size < min_amount:
            logging.warning(
                f"Position size {position_size} < min_amount {min_amount} for {symbol}. Setting to min_amount."
            )
            position_size = min_amount
            
        # Убеждаемся, что сделка больше минимальной стоимости ордера (Bybit требует минимум 5 USDT)
        min_order_value = 5.0
        if position_size * current_price < min_order_value:
            if usdt_balance >= min_order_value / leverage:
                # Нужно чтобы сумма позиции с учетом плеча была больше 5 USDT
                # С запасом делаем 6 USDT
                position_size = 6.0 / current_price
                if step_size > 0:
                    position_size = round(position_size / step_size) * step_size
                    position_size = round(position_size, precision)
                else:
                    position_size = round(position_size + 0.001, 3)
            else:
                logging.warning(f"Insufficient balance to meet 5 USDT min order value for {symbol}")
                return None
                
        # --- ФИКС МАРЖИ ДЛЯ БОТА ---
        # Вычисляем сколько реально маржи мы потратим
        # Если это больше нашего usdt_balance, то уменьшаем позицию
        # Округляем до нужной точности, обрезая лишнее вниз (чтобы не превысить баланс)
        # Для того чтобы 100% не получить ошибку маржи, мы можем использовать еще один коэффициент запаса (например, 0.8)
        # так как Bybit резервирует часть денег под комиссии и начальную маржу при 10x
        # 0.90 может быть недостаточно
        
        # Получаем размер шага из min_amount (это не совсем правильно, 
        # лучше использовать qtyStep, но пока возьмем его как базу)
        step_size = min_amount
        
        # Учитываем кредитное плечо при расчете размера позиции!
        # By default on new unified margin accounts it could be 10x
        leverage = 10 
        
        actual_margin_needed = (position_size * current_price) / leverage
        # Оставляем еще больше запаса (используем 80% от баланса, а не 90%, чтобы точно хватило маржи)
        if actual_margin_needed > (usdt_balance * 0.80):
            logging.warning(f"Needed margin {actual_margin_needed} > available {usdt_balance}. Reducing size...")
            position_size = (usdt_balance * 0.80 * leverage) / current_price 
            if step_size > 0:
                # Считаем количество знаков после запятой в шаге
                step_str = str(step_size)
                if '.' in step_str:
                    precision = len(step_str.split('.')[1].rstrip('0'))
                else:
                    precision = 0
                factor = 10 ** precision
                position_size = int(position_size * factor) / factor
                position_size = round(position_size / step_size) * step_size
                position_size = round(position_size, precision)
            else:
                position_size = round(position_size, 3)
             
            if position_size * current_price < min_order_value:
                logging.warning(f"Cannot trade {symbol}. Too little balance.")
                return None

        # Финальная проверка на то, чтобы маржи ТОЧНО хватило
        # С учетом возможных комиссий (taker fee usually ~0.05-0.06% of NOTIONAL value)
        notional_value = position_size * current_price
        fee = notional_value * 0.0006 * 2 # Вход и выход
        if (notional_value / leverage) + fee > usdt_balance:
            logging.warning(f"Not enough balance after fees for {symbol}")
            return None
            
        if position_size * current_price < min_order_value:
            logging.warning(f"Cannot trade {symbol}. Too little balance.")
            return None

        # --- НОВЫЙ ФИКС ДЛЯ ДЕМО-СЧЕТОВ ---
        # На демо счетах Bybit часто баланс может отображаться, но маржа для деривативов недоступна 
        # или плечо выставлено не в 10x. Вычисляем сколько реально маржи мы потратим
        # Если это больше нашего usdt_balance, то уменьшаем позицию
        actual_margin_needed = (position_size * current_price) / leverage
        if actual_margin_needed > usdt_balance:
            logging.warning(f"Needed margin {actual_margin_needed} > {usdt_balance}. Reducing size...")
            position_size = (usdt_balance * 0.95 * leverage) / current_price 
            if step_size > 0:
                position_size = position_size - (position_size % step_size)
                position_size = round(position_size, precision)
            else:
                position_size = round(position_size, 3)
            
            if position_size * current_price < min_order_value:
                logging.warning(f"Cannot trade {symbol}. Too little balance.")
                return None

        logging.info(
            f"Calculated position size for {symbol}: {position_size} contracts (Risk Margin: {position_size * current_price / leverage:.2f} USDT, Total Value: {position_size * current_price:.2f} USDT)"
        )
        return position_size

    # 2. Недостаточно маржи на аккаунте - ErrCode: 110007 (ab not enough for new order)
    # Чтобы этого избежать, нужно использовать кросс-маржу или правильно рассчитывать стоимость с учетом плеча
    except pybit.exceptions.InvalidRequestError as e:
        if "110007" in str(e):
            logging.error(f"Not enough margin for {symbol} (balance: {usdt_balance} USDT, needed for pos: {position_size * current_price}). Error: {e}")
            return None
        elif "110094" in str(e):
            logging.error(f"Order value too small for {symbol}. Needed 5 USDT minimum.")
            return None
        else:
            logging.error(f"Order error for {symbol}: {e}")
            return None
    except Exception as e:
        # Ignore encoding errors for printing arrows in logs
        if isinstance(e, UnicodeEncodeError):
            pass
        else:
            logging.error(f"Error calculating position size for {symbol}: {e}")
        return None

async def log_trade(trade):
    try:
        async with aiofiles.open('trades_log.json', 'a') as f:
            await f.write(json.dumps(trade) + '\n')
    except Exception as e:
        logging.error(f"Error logging trade: {e}")

async def manage_position(session, symbol, signal, usdt_balance, min_amounts,
                         lstm_model, lstm_scaler, rf_model, rf_scaler):
    TRADE_COOLDOWN = 60
    current_time = time.time()
    async with lock:
        last_time = last_trade_time.get(symbol, 0)
        if current_time - last_time < TRADE_COOLDOWN:
            return
    try:
        position_size = await calculate_position_size(session,
                                                       symbol,
                                                       usdt_balance,
                                                       min_amount=min_amounts.get(
                                                           symbol, 0.1))
        if position_size is None or position_size < min_amounts.get(symbol, 0.1):
            return
            
        response = session.get_tickers(category="linear", symbol=symbol)
        price = float(response['result']['list'][0]['lastPrice'])
        
        if price is None or price <= 0:
            logging.error(f"Current price for {symbol} is missing")
            return
            
        if usdt_balance < (position_size * price):
            logging.warning(
                f"Insufficient USDT balance for {symbol}. Required: {position_size * price}, Available: {usdt_balance}"
            )
            return
            
        df = await get_data_async(session, symbol, timeframe=TIMEFRAME, limit=1000)
        if df is None:
            return
            
        signal_pred = signal
        if signal_pred == 1:
            try:
                # Рассчитываем цены для TP и SL
                take_profit_price = price * (1 + TAKE_PROFIT_PCT)
                stop_loss_price = price * (1 - STOP_LOSS_PCT)
                
                # Округляем цены до нужного количества знаков (как у текущей цены)
                price_str = str(price)
                if '.' in price_str:
                    precision = len(price_str.split('.')[1])
                    take_profit_price = round(take_profit_price, precision)
                    stop_loss_price = round(stop_loss_price, precision)
                
                order = session.place_order(
                    category="linear",
                    symbol=symbol,
                    side="Buy",
                    orderType="Market",
                    qty=str(position_size),
                    takeProfit=str(take_profit_price),
                    stopLoss=str(stop_loss_price),
                    tpslMode="Full" # TP/SL применяется ко всей позиции
                )
                
                # Check success
                if order.get('retCode') != 0:
                    logging.error(f"Order failed for {symbol}. Error: {order}")
                    return
                    
                entry_price = await fetch_average_price(session, symbol)
                if entry_price is not None:
                    trade = {
                        'symbol': symbol,
                        'action': 'buy',
                        'amount': position_size,
                        'price': entry_price,
                        'timestamp': current_time
                    }
                    await log_trade(trade)
                    logging.info(
                        f"Opened LONG position for {symbol} at price {entry_price}. TP: {take_profit_price}, SL: {stop_loss_price}")
            except Exception as e:
                logging.error(f"Error opening long position for {symbol}: {e}")
        elif signal_pred == 0:
            try:
                # Рассчитываем цены для TP и SL для шорта
                take_profit_price = price * (1 - TAKE_PROFIT_PCT)
                stop_loss_price = price * (1 + STOP_LOSS_PCT)
                
                # Округляем цены до нужного количества знаков
                price_str = str(price)
                if '.' in price_str:
                    precision = len(price_str.split('.')[1])
                    take_profit_price = round(take_profit_price, precision)
                    stop_loss_price = round(stop_loss_price, precision)
                    
                order = session.place_order(
                    category="linear",
                    symbol=symbol,
                    side="Sell",
                    orderType="Market",
                    qty=str(position_size),
                    takeProfit=str(take_profit_price),
                    stopLoss=str(stop_loss_price),
                    tpslMode="Full" # TP/SL применяется ко всей позиции
                )
                
                # Check success
                if order.get('retCode') != 0:
                    logging.error(f"Order failed for {symbol}. Error: {order}")
                    return
                    
                entry_price = await fetch_average_price(session, symbol)
                if entry_price is not None:
                    trade = {
                        'symbol': symbol,
                        'action': 'sell',
                        'amount': position_size,
                        'price': entry_price,
                        'timestamp': current_time
                    }
                    await log_trade(trade)
                    logging.info(
                        f"Opened SHORT position for {symbol} at price {entry_price}. TP: {take_profit_price}, SL: {stop_loss_price}")
            except Exception as e:
                logging.error(f"Error opening short position for {symbol}: {e}")
        async with lock:
            last_trade_time[symbol] = current_time
    except Exception as e:
        logging.error(f"Error managing position for {symbol}: {e}")

async def fetch_average_price(session, symbol):
    try:
        response = session.get_tickers(category="linear", symbol=symbol)
        last_price = float(response['result']['list'][0]['lastPrice'])
        return last_price
    except Exception as e:
        logging.error(f"Error fetching average price for {symbol}: {e}")
        return None
