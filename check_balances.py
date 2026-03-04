import json
from pybit.unified_trading import HTTP
from config import API_KEY, API_SECRET

session = HTTP(
    testnet=False,
    demo=True,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

try:
    response = session.get_wallet_balance(accountType="UNIFIED")
    
    print("=== YOUR DEMO BALANCES ===")
    list_data = response.get('result', {}).get('list', [])
    if list_data:
        account_data = list_data[0]
        for k, v in account_data.items():
            if k != 'coin':
                print(f"{k}: {v}")
        print("\nCoins:")
        coins = account_data.get('coin', [])
        for coin in coins:
            print(coin)
    else:
        print("No balance data found in UNIFIED account.")
        
except Exception as e:
    print("Error fetching balance:", e)