#!/usr/bin/env python3
"""KAIROS: Predictive Polymarket Alpha Agent (MVP).

Scans active Polymarket markets, estimates true probabilities, and ranks potential edges.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class Config:
    max_markets: int = 200
    min_volume: float = 50_000
    min_liquidity: float = 10_000
    min_edge: float = 5.0
    max_candidates: int = 20
    top_n: int = 8


@dataclass
class MarketEdge:
    market_id: str
    market_slug: str
    question: str
    category: str | None
    yes_prob_market: float
    agent_prob: float
    edge_pct: float
    conviction: str
    thesis: str
    volume: float
    liquidity: float
    end_date: str | None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_yes_prob(market: dict[str, Any]) -> float:
    outcomes = market.get("outcomes")
    outcome_prices = market.get("outcomePrices")

    if isinstance(outcomes, list) and isinstance(outcome_prices, list) and len(outcomes) == len(outcome_prices):
        for name, price in zip(outcomes, outcome_prices):
            if str(name).strip().lower() == "yes":
                return max(0.0, min(1.0, _to_float(price, 0.5)))

    tokens = market.get("tokens")
    if isinstance(tokens, list):
        for tok in tokens:
            if str(tok.get("outcome", "")).strip().lower() == "yes":
                return max(0.0, min(1.0, _to_float(tok.get("price"), 0.5)))

    return 0.5


def _days_to_resolution(end_date: str | None) -> int:
    if not end_date:
        return 365
    try:
        dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (dt - now).days)
    except ValueError:
        return 365


def _heuristic_prob(market: dict[str, Any], market_yes_prob: float) -> tuple[float, str]:
    volume = _to_float(market.get("volume"), 0.0)
    liquidity = _to_float(market.get("liquidity"), 0.0)
    days = _days_to_resolution(market.get("endDate"))
    category = str(market.get("category") or "").lower()

    adjustment = 0.0
    if liquidity < 30_000:
        adjustment += 0.04
    elif liquidity > 200_000:
        adjustment -= 0.02

    if days > 120:
        adjustment += 0.02
    elif days < 14:
        adjustment -= 0.01

    if "crypto" in category:
        adjustment += 0.015
    if "sports" in category:
        adjustment -= 0.005

    confidence_pull = min(0.04, math.log10(max(volume, 1.0)) / 100)

    if market_yes_prob >= 0.5:
        agent_prob = market_yes_prob - adjustment + confidence_pull
    else:
        agent_prob = market_yes_prob + adjustment - confidence_pull

    agent_prob = max(0.01, min(0.99, agent_prob))
    thesis = (
        "Heuristic estimate adjusted for liquidity, resolution horizon, and category priors; "
        "confidence pull applied toward consensus in high-volume markets."
    )
    return agent_prob, thesis


def _conviction(edge_pct: float) -> str:
    if edge_pct >= 12:
        return "High"
    if edge_pct >= 7:
        return "Medium"
    return "Low"


def _time_decay(days_to_resolution: int) -> float:
    if days_to_resolution <= 30:
        return 1.20
    if days_to_resolution <= 90:
        return 1.0
    return 0.85


def _liquidity_factor(liquidity: float) -> float:
    return max(0.5, min(1.6, math.log10(max(10.0, liquidity)) / 3.0))


def _gamma_get(path: str, params: dict[str, Any], timeout_s: float = 30.0, attempts: int = 3) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"{GAMMA_BASE}{path}?{query}"
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network/data errors
            last_error = exc

    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_active_markets(cfg: Config) -> list[dict[str, Any]]:
    payload = _gamma_get(
        "/markets",
        {
            "active": "true",
            "closed": "false",
            "limit": cfg.max_markets,
            "order": "volume",
            "ascending": "false",
        },
    )
    return payload if isinstance(payload, list) else []


def filter_candidates(markets: list[dict[str, Any]], cfg: Config) -> list[dict[str, Any]]:
    def keep(m: dict[str, Any]) -> bool:
        return (
            _to_float(m.get("volume"), 0) >= cfg.min_volume
            and _to_float(m.get("liquidity"), 0) >= cfg.min_liquidity
            and not bool(m.get("closed", False))
            and bool(m.get("question"))
        )

    filtered = [m for m in markets if keep(m)]
    filtered.sort(key=lambda x: _to_float(x.get("volume"), 0), reverse=True)
    return filtered[: cfg.max_candidates]


async def analyze_market(market: dict[str, Any], cfg: Config, llm_client: Any | None = None) -> MarketEdge:
    del cfg, llm_client
    yes_prob_market = _extract_yes_prob(market)
    agent_prob, thesis = _heuristic_prob(market, yes_prob_market)

    edge_raw = abs(agent_prob - yes_prob_market) * 100
    days = _days_to_resolution(market.get("endDate"))
    liquidity = _to_float(market.get("liquidity"), 0)
    adjusted_edge = edge_raw * _time_decay(days) * _liquidity_factor(liquidity)

    return MarketEdge(
        market_id=str(market.get("id", "")),
        market_slug=str(market.get("slug", "")),
        question=str(market.get("question", "")),
        category=market.get("category"),
        yes_prob_market=yes_prob_market,
        agent_prob=agent_prob,
        edge_pct=round(adjusted_edge, 2),
        conviction=_conviction(adjusted_edge),
        thesis=thesis,
        volume=_to_float(market.get("volume"), 0),
        liquidity=liquidity,
        end_date=market.get("endDate"),
    )


def _print_edges(edges: list[MarketEdge], top_n: int) -> None:
    print(f"\nTop {min(top_n, len(edges))} alpha opportunities")
    print("=" * 80)
    for e in edges[:top_n]:
        print(f"Question: {e.question}")
        print(f"Slug: {e.market_slug}")
        print(f"Market YES: {e.yes_prob_market:.1%} | Agent YES: {e.agent_prob:.1%}")
        print(f"Edge Score: {e.edge_pct:.2f}% | Conviction: {e.conviction}")
        print(f"Vol: ${e.volume:,.0f} | Liq: ${e.liquidity:,.0f} | End: {e.end_date}")
        print(f"Thesis: {e.thesis}")
        print("-" * 80)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="KAIROS Polymarket Alpha Agent")
    p.add_argument("--max-markets", type=int, default=200)
    p.add_argument("--min-volume", type=float, default=50_000)
    p.add_argument("--min-liquidity", type=float, default=10_000)
    p.add_argument("--min-edge", type=float, default=5.0)
    p.add_argument("--max-candidates", type=int, default=20)
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--json-out", type=str, default="")
    return p.parse_args()


async def run(cfg: Config, json_out: str = "") -> list[MarketEdge]:
    try:
        markets = fetch_active_markets(cfg)
    except RuntimeError as exc:
        print(f"Warning: {exc}")
        print("Network unavailable; unable to fetch live Polymarket data in this environment.")
        return []

    candidates = filter_candidates(markets, cfg)
    print(f"Fetched {len(markets)} markets | Candidates after filters: {len(candidates)}")

    tasks = [analyze_market(m, cfg) for m in candidates]
    analyzed = await asyncio.gather(*tasks)

    edges = [e for e in analyzed if e.edge_pct >= cfg.min_edge]
    edges.sort(key=lambda x: x.edge_pct, reverse=True)
    _print_edges(edges, cfg.top_n)

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in edges], f, indent=2)
        print(f"\nSaved {len(edges)} edges to {json_out}")

    return edges


def main() -> None:
    args = parse_args()
    cfg = Config(
        max_markets=args.max_markets,
        min_volume=args.min_volume,
        min_liquidity=args.min_liquidity,
        min_edge=args.min_edge,
        max_candidates=args.max_candidates,
        top_n=args.top,
    )
    asyncio.run(run(cfg, args.json_out))


if __name__ == "__main__":
    main()
