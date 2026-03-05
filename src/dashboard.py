from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.main import build_report, load_dotenv

HTML = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Polymarket + Crypto Alpha Dashboard</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 24px; background: #0b1020; color: #e8ebf5; }
    .card { background: #141b34; border-radius: 14px; padding: 16px; margin-bottom: 16px; }
    input { padding: 8px; border-radius: 8px; border: 1px solid #3f4b77; background: #0f152c; color: #fff; }
    button { padding: 9px 14px; border: 0; border-radius: 8px; background: #4c7dff; color: #fff; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; }
    td, th { border-bottom: 1px solid #2f3b65; padding: 10px; text-align: left; vertical-align: top; }
    .small { opacity: 0.8; font-size: 12px; }
  </style>
</head>
<body>
  <h2>Super Polymarket + Crypto Alpha Dashboard</h2>
  <div class=\"card\">
    <label>Symbols: <input id=\"symbols\" value=\"BTC ETH SOL\" /></label>
    <label>Market limit: <input id=\"marketLimit\" value=\"120\" size=\"6\" /></label>
    <label>Top: <input id=\"top\" value=\"10\" size=\"4\" /></label>
    <button onclick=\"run()\">Run Scan</button>
    <p class=\"small\">Requires CMC_API_KEY in .env or environment.</p>
  </div>

  <div id=\"status\" class=\"card\">Ready.</div>
  <div class=\"card\"><table id=\"results\"></table></div>

<script>
async function run() {
  const symbols = document.getElementById('symbols').value.trim();
  const marketLimit = document.getElementById('marketLimit').value;
  const top = document.getElementById('top').value;
  const status = document.getElementById('status');
  const table = document.getElementById('results');
  status.textContent = 'Loading...';
  table.innerHTML = '';

  try {
    const url = `/api/report?symbols=${encodeURIComponent(symbols)}&market_limit=${encodeURIComponent(marketLimit)}&top=${encodeURIComponent(top)}`;
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok) {
      status.textContent = `Error: ${payload.error || 'unknown'}`;
      return;
    }

    const rows = payload.results || [];
    status.textContent = `Loaded ${rows.length} rows.`;

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
