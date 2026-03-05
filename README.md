# Super Polymarket + Crypto Alpha Agent (Starter)

This repository now contains a **starter agent** that scans Polymarket for unusual setups and combines it with real-time crypto market context from CoinMarketCap.

## What it does

- Pulls active Polymarket markets.
- Flags interesting setups, including:
  - High volume spikes.
  - Wide bid/ask spread (possible inefficiency).
  - Mid-price near 50% (uncertain, often information-rich).
  - Large mismatch between market sentiment and recent crypto move.
- Pulls crypto data from CoinMarketCap (quotes + market pairs).
- Produces a ranked alpha-style briefing in terminal + JSON output.
- Includes a tiny local dashboard with iPhone-friendly tap targets.

## Quickstart (CLI)

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
cp .env.example .env
# edit .env with your key
```

3. Run the CLI:

```bash
python -m src.main --symbols BTC ETH SOL DOGE --market-limit 150 --top 15
```

4. Optional JSON export:

```bash
python -m src.main --symbols BTC ETH SOL --output report.json
```

## Quickstart (Dashboard)

Run a local dashboard server:

```bash
python -m src.dashboard --host 0.0.0.0 --port 8501
```

Then open one of these:
- Same device: `http://127.0.0.1:8501`
- iPhone on same Wi-Fi as your laptop: `http://<YOUR_LAPTOP_IP>:8501`

Use **Preview UI (No API Key)** for instant front-end preview, or **Run Scan (Live Data)** for real data.

## Environment variables

- `CMC_API_KEY`: CoinMarketCap API key.
- `POLYMARKET_GAMMA_URL`: Optional override (default: `https://gamma-api.polymarket.com`).
- `REQUEST_TIMEOUT_SECONDS`: Optional timeout (default: `20`).

## Notes

- This implementation is **read-only analytics** and does not trade.
- It is intended as a base scaffold so we can iterate with more sophisticated signal logic (orderbook, cross-exchange basis, event clustering, and alerting).
