from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings


class PolymarketClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.polymarket_gamma_url.rstrip("/")
        self.timeout = settings.request_timeout_seconds

    def list_markets(self, limit: int = 100, offset: int = 0, active: bool = True) -> list[dict[str, Any]]:
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": "false",
            "archived": "false",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            return data["data"]
        return []


class CoinMarketCapClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = "https://pro-api.coinmarketcap.com"
        self.timeout = settings.request_timeout_seconds
        self.headers = {"X-CMC_PRO_API_KEY": settings.cmc_api_key, "Accept": "application/json"}

    def latest_quotes(self, symbols: list[str]) -> dict[str, Any]:
        symbol_csv = ",".join(s.upper() for s in symbols)
        params = {"symbol": symbol_csv, "convert": "USD"}
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.get(f"{self.base_url}/v1/cryptocurrency/quotes/latest", params=params)
            response.raise_for_status()
            return response.json()

    def market_pairs_latest(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        params = {"symbol": symbol.upper(), "limit": limit}
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.get(f"{self.base_url}/v1/cryptocurrency/market-pairs/latest", params=params)
            response.raise_for_status()
            return response.json()
