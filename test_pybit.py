from pybit.unified_trading import HTTP

session = HTTP(
    testnet=True, # For demo trading, testnet=True or demo=True?
    demo=True,
    api_key="eSLaJxUMfxEATayRbE",
    api_secret="v28DdPI6oa2rPQXrB5z4ibkp3QuN4ENbC733",
)

try:
    print(session.get_wallet_balance(accountType="UNIFIED"))
except Exception as e:
    print("Error:", e)
