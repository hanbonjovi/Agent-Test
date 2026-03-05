from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

try:
    import httpx  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

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
        data = _get_json(f"{self.base_url}/markets", params=params, timeout=self.timeout)
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
        data = _get_json(
            f"{self.base_url}/v1/cryptocurrency/quotes/latest",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        return data if isinstance(data, dict) else {}

    def market_pairs_latest(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        params = {"symbol": symbol.upper(), "limit": limit}
        data = _get_json(
            f"{self.base_url}/v1/cryptocurrency/market-pairs/latest",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        return data if isinstance(data, dict) else {}


def _get_json(url: str, params: dict[str, Any], timeout: float, headers: dict[str, str] | None = None) -> Any:
    if httpx is not None:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    query = urlencode(params)
    final_url = f"{url}?{query}" if query else url
    request = Request(final_url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP error {exc.code}: {msg}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc
