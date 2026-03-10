# KAIROS Polymarket Alpha Agent (MVP)

A read-only predictive scanner that pulls active Polymarket markets and ranks potential pricing inefficiencies ("alpha").

## What you can deploy

You now have **two ways to test**:

1. **Python CLI (fastest for local testing)** using `kairos_alpha.py`.
2. **Cloudflare Worker API (best for shareable cloud testing)** using `cloudflare-worker.mjs` + `wrangler.toml`.

## Local quick start (Python)

```bash
python3 kairos_alpha.py --max-markets 150 --top 10
```

### CLI options

```bash
python3 kairos_alpha.py --help
```

Key options:

- `--max-markets`: max markets fetched from Gamma.
- `--min-volume`: minimum market volume.
- `--min-liquidity`: minimum liquidity.
- `--min-edge`: minimum adjusted edge percentage to keep.
- `--top`: number of opportunities to print.
- `--json-out`: write ranked results to JSON.

Example:

```bash
python3 kairos_alpha.py --max-markets 80 --min-volume 25000 --top 5 --json-out edges.json
```

## Cloudflare test path (from GitHub)

Yes — you can pull this repo from GitHub straight into Cloudflare and test there.

### Option A: Cloudflare dashboard + GitHub integration

1. Push this repo to your GitHub account.
2. In Cloudflare dashboard, go to **Workers & Pages**.
3. Create a **Worker** and connect/import from GitHub.
4. Select this repo and branch.
5. Ensure these files are present at repo root:
   - `cloudflare-worker.mjs`
   - `wrangler.toml`
6. Deploy.
7. Test endpoints:
   - `/health`
   - `/scan?top=5&max_markets=80`

### Option B: Wrangler CLI (direct)

```bash
npm install -g wrangler
wrangler login
wrangler deploy
```

Then test:

```bash
curl "https://<your-worker-subdomain>/health"
curl "https://<your-worker-subdomain>/scan?top=5&max_markets=80"
```

## Worker endpoint behavior

- `GET /health` → simple uptime check.
- `GET /scan` → fetches active Gamma markets, applies the same heuristic logic as the Python scanner, and returns ranked JSON edges.
- Query params accepted by `/scan`:
  - `max_markets`
  - `min_volume`
  - `min_liquidity`
  - `min_edge`
  - `max_candidates`
  - `top`

## Notes

- This MVP is **read-only** and **not auto-trading**.
- Always review market resolution criteria before taking positions.
- If Gamma API is temporarily blocked/rate-limited from a network, the scanner will return an error response.
