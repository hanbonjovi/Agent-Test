import asyncio

import pytest

from kairos_alpha import Config, _extract_yes_prob, _heuristic_prob, analyze_market, filter_candidates


def test_extract_yes_prob_from_outcomes_and_prices():
    market = {"outcomes": ["No", "Yes"], "outcomePrices": [0.63, 0.37]}
    assert _extract_yes_prob(market) == pytest.approx(0.37)


def test_extract_yes_prob_from_tokens_shape():
    market = {"tokens": [{"outcome": "NO", "price": 0.8}, {"outcome": "YES", "price": 0.2}]}
    assert _extract_yes_prob(market) == pytest.approx(0.2)


def test_filter_candidates_applies_thresholds():
    cfg = Config(min_volume=100, min_liquidity=50)
    markets = [
        {"question": "A", "volume": 101, "liquidity": 55, "closed": False},
        {"question": "B", "volume": 99, "liquidity": 55, "closed": False},
    ]
    out = filter_candidates(markets, cfg)
    assert len(out) == 1
    assert out[0]["question"] == "A"


def test_analyze_market_returns_non_negative_edge():
    cfg = Config()
    market = {
        "id": "1",
        "slug": "test",
        "question": "Will X happen?",
        "outcomes": ["Yes", "No"],
        "outcomePrices": [0.45, 0.55],
        "volume": 50000,
        "liquidity": 50000,
        "category": "Crypto",
        "endDate": "2030-01-01T00:00:00Z",
    }
    edge = asyncio.run(analyze_market(market, cfg))
    assert edge.edge_pct >= 0
    assert edge.yes_prob_market == pytest.approx(0.45)


def test_heuristic_prob_bounded():
    market = {"volume": 1_000_000, "liquidity": 500, "category": "Crypto", "endDate": "2031-01-01T00:00:00Z"}
    prob, _ = _heuristic_prob(market, 0.9)
    assert 0.01 <= prob <= 0.99
