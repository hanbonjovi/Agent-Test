from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv() -> None:
        return None

try:
    from rich.console import Console
    from rich.table import Table
except ModuleNotFoundError:  # pragma: no cover
    Console = None
    Table = None

from src.analysis import enrich_signals_with_crypto_context, parse_crypto_snapshots, score_markets
from src.clients import CoinMarketCapClient, PolymarketClient
from src.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Super Polymarket + Crypto Alpha Agent")
    parser.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "SOL"], help="Crypto symbols")
    parser.add_argument("--market-limit", type=int, default=120, help="Polymarket market fetch limit")
    parser.add_argument("--top", type=int, default=10, help="Top signals to display")
    parser.add_argument("--output", type=str, default="", help="Optional output JSON path")
    return parser.parse_args()


def render_console_report(enriched: list[dict], top: int) -> None:
    if Console is None or Table is None:
        for row in enriched[:top]:
            market = row["market"]
            print(f"[{row['signal_score']:.2f}] {row['question']}")
            print(
                f"  yes={market['yes_price']} spread={market['spread']} volume={market['volume']:.0f} reasons={'; '.join(row['reasons'])}"
            )
        return

    console = Console()
    table = Table(title="Top Polymarket + Crypto Alpha Setups")
    table.add_column("Score", justify="right")
    table.add_column("Market")
    table.add_column("Yes")
    table.add_column("Spread")
    table.add_column("Vol")
    table.add_column("Crypto")
    table.add_column("Reasons")

    for row in enriched[:top]:
        crypto = row.get("crypto_context")
        crypto_str = "-"
        if crypto:
            crypto_str = f"{crypto['symbol']} ${crypto['price']:.2f} ({crypto['percent_change_24h']:+.2f}%)"

        m = row["market"]
        table.add_row(
            f"{row['signal_score']:.2f}",
            row["question"][:72],
            "-" if m["yes_price"] is None else f"{m['yes_price']:.3f}",
            "-" if m["spread"] is None else f"{m['spread']:.3f}",
            f"{m['volume']:.0f}",
            crypto_str,
            "; ".join(row["reasons"][:3]),
        )

    console.print(table)


def build_report(symbols: list[str], market_limit: int, top: int) -> list[dict]:
    settings = Settings.from_env()
    poly = PolymarketClient(settings)
    cmc = CoinMarketCapClient(settings)

    markets = poly.list_markets(limit=market_limit)
    scored = score_markets(markets)

    quotes = cmc.latest_quotes(symbols)
    crypto = parse_crypto_snapshots(quotes)

    enriched = enrich_signals_with_crypto_context(scored, crypto)
    return enriched[:top]


def main() -> None:
    load_dotenv()
    args = parse_args()
    report = build_report(args.symbols, args.market_limit, args.top)

    render_console_report(report, args.top)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
