from __future__ import annotations

from typing import Any

from src.models import CryptoSnapshot, MarketSignal


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_crypto_snapshots(cmc_quotes_payload: dict[str, Any]) -> list[CryptoSnapshot]:
    data = cmc_quotes_payload.get("data", {})
    snapshots: list[CryptoSnapshot] = []

    for symbol, blob in data.items():
        quote = (blob or {}).get("quote", {}).get("USD", {})
        price = _to_float(quote.get("price"))
        change_24h = _to_float(quote.get("percent_change_24h"))
        vol_24h = _to_float(quote.get("volume_24h"))
        cap = _to_float(quote.get("market_cap"))
        if None in (price, change_24h, vol_24h, cap):
            continue

        snapshots.append(
            CryptoSnapshot(
                symbol=symbol,
                price=price,
                percent_change_24h=change_24h,
                volume_24h=vol_24h,
                market_cap=cap,
            )
        )

    return snapshots


def score_markets(markets: list[dict[str, Any]]) -> list[MarketSignal]:
    scored: list[MarketSignal] = []

    for m in markets:
        question = str(m.get("question") or m.get("title") or "Unknown market")
        market_id = str(m.get("id") or m.get("marketId") or "")
        slug = str(m.get("slug") or "")

        volume = _to_float(m.get("volume") or m.get("volumeNum")) or 0.0
        liquidity = _to_float(m.get("liquidity") or m.get("liquidityNum")) or 0.0

        best_bid = _to_float(m.get("bestBid"))
        best_ask = _to_float(m.get("bestAsk"))
        last = _to_float(m.get("lastTradePrice"))

        yes_price = last if last is not None else None
        no_price = 1 - yes_price if yes_price is not None and 0 <= yes_price <= 1 else None

        spread = None
        if best_bid is not None and best_ask is not None:
            spread = max(0.0, best_ask - best_bid)

        reasons: list[str] = []
        score = 0.0

        if volume > 250_000:
            reasons.append("High traded volume")
            score += 2.5
        elif volume > 75_000:
            reasons.append("Rising volume")
            score += 1.4

        if liquidity < 25_000 and volume > 50_000:
            reasons.append("High volume vs low liquidity (possible inefficiency)")
            score += 1.3

        zone_50 = False
        if yes_price is not None and 0.43 <= yes_price <= 0.57:
            zone_50 = True
            reasons.append("Price near 50% (high uncertainty)")
            score += 1.1

        if spread is not None and spread >= 0.08:
            reasons.append("Wide spread")
            score += 1.2

        if "bitcoin" in question.lower() or "btc" in question.lower():
            reasons.append("Crypto-linked narrative")
            score += 0.8

        if score <= 0:
            continue

        scored.append(
            MarketSignal(
                market_id=market_id,
                question=question,
                slug=slug,
                volume=volume,
                liquidity=liquidity,
                yes_price=yes_price,
                no_price=no_price,
                spread=spread,
                confidence_zone_50=zone_50,
                signal_score=round(score, 3),
                reasons=reasons,
                raw=m,
            )
        )

    return sorted(scored, key=lambda s: s.signal_score, reverse=True)


def enrich_signals_with_crypto_context(
    signals: list[MarketSignal],
    crypto: list[CryptoSnapshot],
) -> list[dict[str, Any]]:
    by_symbol = {c.symbol.upper(): c for c in crypto}
    enriched: list[dict[str, Any]] = []

    for signal in signals:
        lower_q = signal.question.lower()
        matched = None
        for sym in by_symbol:
            if sym.lower() in lower_q or (sym == "BTC" and "bitcoin" in lower_q):
                matched = by_symbol[sym]
                break

        entry = {
            "market_id": signal.market_id,
            "question": signal.question,
            "slug": signal.slug,
            "signal_score": signal.signal_score,
            "reasons": signal.reasons,
            "market": {
                "yes_price": signal.yes_price,
                "no_price": signal.no_price,
                "spread": signal.spread,
                "volume": signal.volume,
                "liquidity": signal.liquidity,
            },
            "crypto_context": None,
        }

        if matched:
            entry["crypto_context"] = {
                "symbol": matched.symbol,
                "price": matched.price,
                "percent_change_24h": matched.percent_change_24h,
                "volume_24h": matched.volume_24h,
                "market_cap": matched.market_cap,
            }
            if abs(matched.percent_change_24h) >= 5 and signal.confidence_zone_50:
                entry["reasons"] = list(entry["reasons"]) + [
                    "Mismatch: large 24h crypto move while prediction remains near 50%"
                ]
                entry["signal_score"] = round(entry["signal_score"] + 0.9, 3)

        enriched.append(entry)

    return sorted(enriched, key=lambda e: e["signal_score"], reverse=True)
