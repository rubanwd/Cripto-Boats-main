import time
import hmac
import hashlib
import json
import logging
import requests
import aiohttp
import asyncio
from urllib.parse import urlencode
from typing import Dict, Any, Optional

class AsyncBybitAPI:
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = ""):
        self.base = base_url.rstrip("/")
        self.key = api_key or ""
        self.secret = api_secret or ""
        self.session = None

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_tickers(self, category="linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return await self._get("/v5/market/tickers", params)

    async def get_kline(self, category="linear", symbol="BTCUSDT", interval="60", limit=200) -> Dict[str, Any]:
        params = {"category": category, "symbol": symbol, "interval": str(interval), "limit": str(limit)}
        return await self._get("/v5/market/kline", params)

    async def get_instruments_info(self, category="linear") -> Dict[str, Any]:
        params = {"category": category}
        return await self._get("/v5/market/instruments-info", params)

    async def get_wallet_balance(self, accountType="UNIFIED", coin: str="USDT") -> Dict[str, Any]:
        params = {"accountType": accountType, "coin": coin}
        return await self._get("/v5/account/wallet-balance", params, auth=True)

    async def place_order(self, **kwargs) -> Dict[str, Any]:
        return await self._post("/v5/order/create", kwargs, auth=True)

    async def _get(self, path: str, params: Dict[str, Any], auth: bool = False) -> Dict[str, Any]:
        await self.init_session()
        url = self.base + path
        
        # We need to sync time if auth is required
        ts = str(int(time.time() * 1000))
        
        headers = {}
        if auth:
            # Get server time to avoid timestamp error
            try:
                async with self.session.get(self.base + "/v5/market/time") as time_resp:
                    if time_resp.status == 200:
                        t_data = await time_resp.json()
                        ts = str(t_data['time'])
            except Exception:
                pass
                
            headers = self._auth_headers_get(params, ts)
            
        async with self.session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            if response.status != 200 or data.get('retCode', 0) != 0:
                logging.error(f"Bybit API Error (GET {path}): {data}")
            return data

    async def _post(self, path: str, body: Dict[str, Any], auth: bool = False) -> Dict[str, Any]:
        await self.init_session()
        url = self.base + path
        
        ts = str(int(time.time() * 1000))
        
        headers = {"Content-Type": "application/json"}
        if auth:
            # Get server time to avoid timestamp error
            try:
                async with self.session.get(self.base + "/v5/market/time") as time_resp:
                    if time_resp.status == 200:
                        t_data = await time_resp.json()
                        ts = str(t_data['time'])
            except Exception:
                pass
                
            headers.update(self._auth_headers_post(body, ts))
            
        async with self.session.post(url, json=body, headers=headers) as response:
            data = await response.json()
            if response.status != 200 or data.get('retCode', 0) != 0:
                logging.error(f"Bybit API Error (POST {path}): {data}")
            return data

    def _auth_headers_get(self, params: Dict[str, Any], ts: str) -> Dict[str, str]:
        recv_window = "60000"
        query_str = urlencode(sorted(params.items())) if params else ""
        to_sign = ts + self.key + recv_window + query_str
        sign = hmac.new(self.secret.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.key,
            "X-BAPI-SIGN": sign,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv_window,
        }

    def _auth_headers_post(self, payload: Dict[str, Any], ts: str) -> Dict[str, str]:
        recv_window = "60000"
        body_str = json.dumps(payload) if payload else ""
        to_sign = ts + self.key + recv_window + body_str
        sign = hmac.new(self.secret.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.key,
            "X-BAPI-SIGN": sign,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv_window,
        }
