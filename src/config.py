from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cmc_api_key: str
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    request_timeout_seconds: float = 20.0


    @staticmethod
    def from_env() -> "Settings":
        cmc_api_key = os.getenv("CMC_API_KEY", "").strip()
        if not cmc_api_key:
            raise ValueError("Missing CMC_API_KEY in environment.")

        polymarket_gamma_url = os.getenv(
            "POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com"
        ).strip()

        timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "20").strip()
        try:
            request_timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be a float") from exc

        return Settings(
            cmc_api_key=cmc_api_key,
            polymarket_gamma_url=polymarket_gamma_url,
            request_timeout_seconds=request_timeout_seconds,
        )
