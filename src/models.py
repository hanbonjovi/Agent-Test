from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MarketSignal:
    market_id: str
    question: str
    slug: str
    volume: float
    liquidity: float
    yes_price: float | None
    no_price: float | None
    spread: float | None
    confidence_zone_50: bool
    signal_score: float
    reasons: list[str]
    raw: dict[str, Any]


@dataclass
class CryptoSnapshot:
    symbol: str
    price: float
    percent_change_24h: float
    volume_24h: float
    market_cap: float
