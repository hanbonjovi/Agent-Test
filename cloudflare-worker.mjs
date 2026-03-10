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

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { 'content-type': 'application/json' },
      });
    }

    if (url.pathname !== '/scan') {
      return new Response('Use /scan or /health', { status: 404 });
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
