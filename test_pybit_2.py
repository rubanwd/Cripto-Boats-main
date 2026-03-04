from pybit.unified_trading import HTTP

try:
    session = HTTP(
        demo=True,
        api_key="eSLaJxUMfxEATayRbE",
        api_secret="v28DdPI6oa2rPQXrB5z4ibkp3QuN4ENbC733",
    )
    print("Balance:", session.get_wallet_balance(accountType="UNIFIED"))
except Exception as e:
    print("Error demo=True:", repr(e))

try:
    session2 = HTTP(
        testnet=True,
        api_key="eSLaJxUMfxEATayRbE",
        api_secret="v28DdPI6oa2rPQXrB5z4ibkp3QuN4ENbC733",
    )
    print("Balance testnet:", session2.get_wallet_balance(accountType="UNIFIED"))
except Exception as e:
    print("Error testnet=True:", repr(e))
