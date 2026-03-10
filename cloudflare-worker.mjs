const GAMMA_BASE = 'https://gamma-api.polymarket.com';

function toFloat(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function extractYesProb(market) {
  const outcomes = market?.outcomes;
  const outcomePrices = market?.outcomePrices;

  if (Array.isArray(outcomes) && Array.isArray(outcomePrices) && outcomes.length === outcomePrices.length) {
    for (let i = 0; i < outcomes.length; i += 1) {
      if (String(outcomes[i]).trim().toLowerCase() === 'yes') {
        return Math.min(1, Math.max(0, toFloat(outcomePrices[i], 0.5)));
      }
    }
  }

  const tokens = market?.tokens;
  if (Array.isArray(tokens)) {
    for (const tok of tokens) {
      if (String(tok?.outcome || '').trim().toLowerCase() === 'yes') {
        return Math.min(1, Math.max(0, toFloat(tok?.price, 0.5)));
      }
    }
  }

  return 0.5;
}

function daysToResolution(endDate) {
  if (!endDate) return 365;
  const target = new Date(endDate);
  if (Number.isNaN(target.getTime())) return 365;
  const diffMs = target.getTime() - Date.now();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

function heuristicProb(market, marketYesProb) {
  const volume = toFloat(market?.volume, 0);
  const liquidity = toFloat(market?.liquidity, 0);
  const days = daysToResolution(market?.endDate);
  const category = String(market?.category || '').toLowerCase();

  let adjustment = 0;
  if (liquidity < 30_000) adjustment += 0.04;
  else if (liquidity > 200_000) adjustment -= 0.02;

  if (days > 120) adjustment += 0.02;
  else if (days < 14) adjustment -= 0.01;

  if (category.includes('crypto')) adjustment += 0.015;
  if (category.includes('sports')) adjustment -= 0.005;

  const confidencePull = Math.min(0.04, Math.log10(Math.max(volume, 1)) / 100);

  let agentProb;
  if (marketYesProb >= 0.5) {
    agentProb = marketYesProb - adjustment + confidencePull;
  } else {
    agentProb = marketYesProb + adjustment - confidencePull;
  }

  return Math.min(0.99, Math.max(0.01, agentProb));
}

function timeDecay(days) {
  if (days <= 30) return 1.2;
  if (days <= 90) return 1.0;
  return 0.85;
}

function liquidityFactor(liquidity) {
  return Math.max(0.5, Math.min(1.6, Math.log10(Math.max(10, liquidity)) / 3));
}

function conviction(edgePct) {
  if (edgePct >= 12) return 'High';
  if (edgePct >= 7) return 'Medium';
  return 'Low';
}

function asIntParam(url, key, fallback) {
  const raw = url.searchParams.get(key);
  if (raw === null) return fallback;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

function asFloatParam(url, key, fallback) {
  const raw = url.searchParams.get(key);
  if (raw === null) return fallback;
  const n = parseFloat(raw);
  return Number.isFinite(n) ? n : fallback;
}

function renderHome() {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KAIROS Alpha Scanner</title>
    <style>
      :root { color-scheme: dark; }
      body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; margin: 0; background: #0b1020; color: #e6ecff; }
      .wrap { max-width: 980px; margin: 0 auto; padding: 20px; }
      .card { background: #121a33; border: 1px solid #233059; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
      h1 { margin: 0 0 6px; font-size: 24px; }
      p { margin: 4px 0 12px; color: #a6b3d9; }
      form { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; align-items: end; }
      label { display: grid; font-size: 12px; gap: 6px; }
      input { background: #0c1430; border: 1px solid #2b3b70; border-radius: 8px; color: #e6ecff; padding: 8px; }
      button { background: #4c7eff; border: 0; border-radius: 8px; padding: 10px 12px; color: white; font-weight: 600; cursor: pointer; }
      button.secondary { background: #2a355f; }
      .row { display: flex; gap: 10px; flex-wrap: wrap; }
      pre { background: #0a1128; border: 1px solid #2a365f; border-radius: 10px; padding: 12px; overflow: auto; max-height: 460px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 8px; border-bottom: 1px solid #263663; font-size: 13px; }
      .muted { color: #9db0df; font-size: 12px; }
      .error { color: #ff9aa9; white-space: pre-wrap; }
      .pill { border-radius: 999px; padding: 2px 8px; font-size: 12px; background: #24315a; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h1>KAIROS Alpha Scanner</h1>
        <p>Adjust filters and run live scans from Polymarket Gamma.</p>
        <form id="scanForm">
          <label>Top <input type="number" name="top" value="8" min="1" max="50" /></label>
          <label>Max markets <input type="number" name="max_markets" value="100" min="10" max="500" /></label>
          <label>Min volume <input type="number" name="min_volume" value="50000" min="0" /></label>
          <label>Min liquidity <input type="number" name="min_liquidity" value="10000" min="0" /></label>
          <label>Min edge <input type="number" name="min_edge" value="5" min="0" step="0.1" /></label>
          <label>Max candidates <input type="number" name="max_candidates" value="20" min="1" max="200" /></label>
          <div class="row">
            <button type="submit">Run scan</button>
            <button type="button" class="secondary" id="copyLink">Copy API URL</button>
          </div>
        </form>
        <div class="muted" id="status">Ready.</div>
      </div>

      <div class="card">
        <table id="edgesTable">
          <thead>
            <tr>
              <th>Question</th>
              <th>Edge %</th>
              <th>Conviction</th>
              <th>Market YES</th>
              <th>Agent YES</th>
            </tr>
          </thead>
          <tbody><tr><td colspan="5" class="muted">Run a scan to view results.</td></tr></tbody>
        </table>
      </div>

      <div class="card">
        <div class="row" style="justify-content:space-between;align-items:center;">
          <strong>Raw JSON</strong>
        </div>
        <pre id="jsonOut">{}</pre>
      </div>
    </div>

    <script>
      const form = document.getElementById('scanForm');
      const statusEl = document.getElementById('status');
      const jsonOut = document.getElementById('jsonOut');
      const tbody = document.querySelector('#edgesTable tbody');

      function paramsFromForm() {
        const fd = new FormData(form);
        const params = new URLSearchParams();
        for (const [k, v] of fd.entries()) params.set(k, String(v));
        return params;
      }

      function renderTable(edges) {
        if (!edges.length) {
          tbody.innerHTML = '<tr><td colspan="5" class="muted">No edges found for current filters.</td></tr>';
          return;
        }
        tbody.innerHTML = edges.map((e) => 
          '<tr>' +
          '<td>' + e.question + '</td>' +
          '<td>' + e.edge_pct + '</td>' +
          '<td><span class="pill">' + e.conviction + '</span></td>' +
          '<td>' + (e.yes_prob_market * 100).toFixed(1) + '%</td>' +
          '<td>' + (e.agent_prob * 100).toFixed(1) + '%</td>' +
          '</tr>'
        ).join('');
      }

      async function runScan() {
        const params = paramsFromForm();
        const url = '/scan?' + params.toString();
        statusEl.textContent = 'Loading...';
        try {
          const resp = await fetch(url);
          const data = await resp.json();
          if (!resp.ok) throw new Error(JSON.stringify(data, null, 2));
          statusEl.textContent = 'Loaded ' + data.returned + ' results from ' + data.total_markets + ' markets.';
          jsonOut.textContent = JSON.stringify(data, null, 2);
          renderTable(data.edges || []);
          history.replaceState(null, '', '/?' + params.toString());
        } catch (err) {
          statusEl.innerHTML = '<span class="error">Request failed. ' + String(err) + '</span>';
          jsonOut.textContent = String(err);
          tbody.innerHTML = '<tr><td colspan="5" class="error">Request failed. See details above.</td></tr>';
        }
      }

      form.addEventListener('submit', (e) => {
        e.preventDefault();
        runScan();
      });

      document.getElementById('copyLink').addEventListener('click', async () => {
        const url = location.origin + '/scan?' + paramsFromForm().toString();
        try { await navigator.clipboard.writeText(url); statusEl.textContent = 'Copied: ' + url; }
        catch { statusEl.textContent = 'Copy failed. URL: ' + url; }
      });

      const qs = new URLSearchParams(location.search);
      for (const [k, v] of qs.entries()) {
        const input = form.querySelector('[name="' + k + '"]');
        if (input) input.value = v;
      }
      runScan();
    </script>
  </body>
</html>`;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === '/' || url.pathname === '/index.html') {
      return new Response(renderHome(), {
        headers: { 'content-type': 'text/html; charset=utf-8' },
      });
    }

    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { 'content-type': 'application/json' },
      });
    }

    if (url.pathname !== '/scan') {
      return new Response('Use / for UI, /scan for API, or /health', { status: 404 });
    }

    const cfg = {
      maxMarkets: asIntParam(url, 'max_markets', 100),
      minVolume: asFloatParam(url, 'min_volume', 50_000),
      minLiquidity: asFloatParam(url, 'min_liquidity', 10_000),
      minEdge: asFloatParam(url, 'min_edge', 5),
      maxCandidates: asIntParam(url, 'max_candidates', 20),
      top: asIntParam(url, 'top', 8),
    };

    const gamma = new URL('/markets', GAMMA_BASE);
    gamma.searchParams.set('active', 'true');
    gamma.searchParams.set('closed', 'false');
    gamma.searchParams.set('limit', String(cfg.maxMarkets));
    gamma.searchParams.set('order', 'volume');
    gamma.searchParams.set('ascending', 'false');

    let markets;
    try {
      const resp = await fetch(gamma, { cf: { cacheTtl: 30, cacheEverything: false } });
      if (!resp.ok) {
        return new Response(JSON.stringify({ error: `Gamma returned ${resp.status}` }), {
          status: 502,
          headers: { 'content-type': 'application/json' },
        });
      }
      markets = await resp.json();
      if (!Array.isArray(markets)) markets = [];
    } catch (err) {
      return new Response(JSON.stringify({ error: `Gamma fetch failed: ${String(err)}` }), {
        status: 502,
        headers: { 'content-type': 'application/json' },
      });
    }

    const candidates = markets
      .filter((m) => toFloat(m?.volume, 0) >= cfg.minVolume)
      .filter((m) => toFloat(m?.liquidity, 0) >= cfg.minLiquidity)
      .filter((m) => !m?.closed)
      .filter((m) => Boolean(m?.question))
      .sort((a, b) => toFloat(b?.volume, 0) - toFloat(a?.volume, 0))
      .slice(0, cfg.maxCandidates);

    const edges = candidates
      .map((market) => {
        const yesProbMarket = extractYesProb(market);
        const agentProb = heuristicProb(market, yesProbMarket);
        const edgeRaw = Math.abs(agentProb - yesProbMarket) * 100;
        const days = daysToResolution(market?.endDate);
        const liquidity = toFloat(market?.liquidity, 0);
        const edgePct = edgeRaw * timeDecay(days) * liquidityFactor(liquidity);

        return {
          market_id: String(market?.id || ''),
          market_slug: String(market?.slug || ''),
          question: String(market?.question || ''),
          category: market?.category || null,
          yes_prob_market: yesProbMarket,
          agent_prob: Math.min(0.99, Math.max(0.01, agentProb)),
          edge_pct: Number(edgePct.toFixed(2)),
          conviction: conviction(edgePct),
          thesis:
            'Heuristic estimate adjusted for liquidity, resolution horizon, and category priors; confidence pull applied toward consensus in high-volume markets.',
          volume: toFloat(market?.volume, 0),
          liquidity,
          end_date: market?.endDate || null,
        };
      })
      .filter((e) => e.edge_pct >= cfg.minEdge)
      .sort((a, b) => b.edge_pct - a.edge_pct)
      .slice(0, cfg.top);

    return new Response(
      JSON.stringify(
        {
          config: cfg,
          total_markets: markets.length,
          candidates: candidates.length,
          returned: edges.length,
          edges,
        },
        null,
        2,
      ),
      { headers: { 'content-type': 'application/json' } },
    );
  },
};
