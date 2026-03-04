from pybit.unified_trading import HTTP
import json
from config import API_KEY, API_SECRET

session = HTTP(
    testnet=True,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

try:
    response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    print(json.dumps(response, indent=2))
except Exception as e:
    print("Error:", e)
