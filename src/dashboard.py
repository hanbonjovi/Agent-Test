from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.main import build_report, load_dotenv

SAMPLE_RESULTS = [
    {
        "signal_score": 5.6,
        "question": "Will Bitcoin hit $120k before Jan 1, 2027?",
        "market": {
            "yes_price": 0.51,
            "spread": 0.09,
            "volume": 412340.0,
        },
        "crypto_context": {
            "symbol": "BTC",
            "price": 103245.42,
            "percent_change_24h": 6.8,
        },
        "reasons": [
            "High traded volume",
            "Wide spread",
            "Price near 50% (high uncertainty)",
        ],
    },
    {
        "signal_score": 4.2,
        "question": "Will ETH ETF inflows exceed $2B this month?",
        "market": {
            "yes_price": 0.47,
            "spread": 0.07,
            "volume": 155000.0,
        },
        "crypto_context": {
            "symbol": "ETH",
            "price": 3842.11,
            "percent_change_24h": 4.1,
        },
        "reasons": ["Rising volume", "Price near 50% (high uncertainty)", "Crypto-linked narrative"],
    },
]

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Polymarket + Crypto Alpha Dashboard</title>
  <style>
    :root {
      --bg: #0b1020;
      --card: #141b34;
      --text: #e8ebf5;
      --line: #2f3b65;
      --accent: #4c7dff;
      --accent-2: #3f4b77;
      --accent-preview: #6d52ff;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
      margin: 0;
      padding: 16px;
      background: var(--bg);
      color: var(--text);
      line-height: 1.35;
    }
    h2 { margin: 0 0 12px; font-size: 24px; }
    .card {
      background: var(--card);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 14px;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
      margin-top: 8px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 14px;
      font-weight: 600;
    }
    input {
      width: 100%;
      min-height: 48px;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--accent-2);
      background: #0f152c;
      color: #fff;
      font-size: 16px;
    }
    .btn-row {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    button {
      width: 100%;
      min-height: 52px;
      padding: 12px 14px;
      border: 0;
      border-radius: 12px;
      color: #fff;
      font-size: 17px;
      font-weight: 700;
      cursor: pointer;
    }
    #runBtn { background: var(--accent); }
    #previewBtn { background: var(--accent-preview); }
    .small { opacity: 0.86; font-size: 13px; margin: 8px 0 0; }
    .hint { margin: 0; font-size: 13px; opacity: .9; }
    .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    table { width: 100%; border-collapse: collapse; min-width: 760px; }
    td, th {
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }
    @media (min-width: 760px) {
      body { padding: 24px; }
      .controls {
        grid-template-columns: 1.4fr 1fr 0.8fr;
        align-items: end;
      }
      .run-btn-wrap { grid-column: 1 / -1; }
      .btn-row { grid-template-columns: repeat(2, minmax(220px, 280px)); }
    }
  </style>
</head>
<body>
  <h2>Super Polymarket + Crypto Alpha Dashboard</h2>
  <div class="card">
    <p class="hint">Tap <strong>Preview UI</strong> to see a front-end sample instantly, or <strong>Run Scan</strong> for live data.</p>
    <div class="controls">
      <label>
        Symbols
        <input id="symbols" value="BTC ETH SOL" inputmode="text" autocapitalize="characters" />
      </label>
      <label>
        Market limit
        <input id="marketLimit" value="120" inputmode="numeric" pattern="[0-9]*" />
      </label>
      <label>
        Top results
        <input id="top" value="10" inputmode="numeric" pattern="[0-9]*" />
      </label>
      <div class="run-btn-wrap btn-row">
        <button id="previewBtn" onclick="previewUi()">Preview UI (No API Key)</button>
        <button id="runBtn" onclick="runScan()">Run Scan (Live Data)</button>
      </div>
    </div>
    <p class="small">Live mode requires CMC_API_KEY in .env or environment.</p>
  </div>

  <div id="status" class="card">Ready.</div>
  <div class="card table-wrap"><table id="results"></table></div>

<script>
function renderRows(rows) {
  const table = document.getElementById('results');
  table.innerHTML = `<thead><tr><th>Score</th><th>Market</th><th>Yes</th><th>Spread</th><th>Volume</th><th>Crypto</th><th>Reasons</th></tr></thead>`;
  const tbody = document.createElement('tbody');
  for (const row of rows) {
    const m = row.market || {};
    const c = row.crypto_context;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.signal_score}</td><td>${row.question}</td><td>${m.yes_price ?? '-'}</td><td>${m.spread ?? '-'}</td><td>${m.volume ?? '-'}</td><td>${c ? `${c.symbol} $${Number(c.price).toFixed(2)} (${Number(c.percent_change_24h).toFixed(2)}%)` : '-'}</td><td>${(row.reasons || []).join('; ')}</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

async function previewUi() {
  const status = document.getElementById('status');
  status.textContent = 'Loading preview...';
  try {
    const response = await fetch('/api/preview');
    const payload = await response.json();
    if (!response.ok) {
      status.textContent = `Error: ${payload.error || 'unknown'}`;
      return;
    }
    const rows = payload.results || [];
    status.textContent = `Preview loaded (${rows.length} sample rows).`;
    renderRows(rows);
  } catch (err) {
    status.textContent = `Preview failed: ${err}`;
  }
}

async function runScan() {
  const symbols = document.getElementById('symbols').value.trim();
  const marketLimit = document.getElementById('marketLimit').value;
  const top = document.getElementById('top').value;
  const status = document.getElementById('status');
  status.textContent = 'Loading live scan...';

  try {
    const url = `/api/report?symbols=${encodeURIComponent(symbols)}&market_limit=${encodeURIComponent(marketLimit)}&top=${encodeURIComponent(top)}`;
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok) {
      status.textContent = `Error: ${payload.error || 'unknown'}`;
      return;
    }
    const rows = payload.results || [];
    status.textContent = `Live scan loaded ${rows.length} rows.`;
    renderRows(rows);
  } catch (err) {
    status.textContent = `Request failed: ${err}`;
  }
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return

        if parsed.path == "/api/preview":
            self._send_json({"results": SAMPLE_RESULTS})
            return

        if parsed.path == "/api/report":
            try:
                params = parse_qs(parsed.query)
                symbols = (params.get("symbols", ["BTC ETH SOL"])[0]).replace(",", " ").split()
                market_limit = int(params.get("market_limit", ["120"])[0])
                top = int(params.get("top", ["10"])[0])
                result = build_report(symbols=symbols, market_limit=market_limit, top=top)
                self._send_json({"results": result})
            except Exception as exc:  # pragma: no cover
                self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json({"error": "Not found"}, status=404)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local dashboard for Polymarket + CMC alpha scan")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
