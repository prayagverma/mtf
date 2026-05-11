# MTF Analytics — Production Build (v4)

A static dashboard visualising daily Margin Trading Facility (MTF) data for NSE & BSE. Designed for direct deployment to **Cloudflare Pages**.

- **Stack**: Vanilla HTML + CSS + JS (no build step), Oat UI 0.6.1, TradingView Lightweight Charts 5.2.0, Inter / JetBrains Mono via Google Fonts.
- **Data**: 2,178 unique trading days (2017-06-22 → 2026-05-07) plus 5,210 stock-level series (gzipped, progressively loaded).
- **Design**: Minimalist, bold typography, professional. Light + dark themes.
- **Total payload**: ~1.0 MB on first load (60 KB HTML + 870 KB JSON). Stock-level chunks (~8 MB) load only when a stock is charted.

## Folder contents

| File | Role |
|---|---|
| `index.html` | Single-page app — header, controls, tabs, charts, stock search |
| `404.html` | Branded 404 page (auto-served by Cloudflare Pages on missing routes) |
| `mtf_daily_totals.json` | Long-format daily totals; sanitized + trimmed |
| `compressed_data/manifest.json` | Manifest pointing at the gzipped chunks |
| `compressed_data/stock_analytics_base.json.gz` | Stock index + latest snapshot for tabs |
| `compressed_data/stock_data_chunk_{1,2}.json.gz` | Per-stock daily series, loaded on demand |
| `_headers` | Cloudflare Pages — security & cache headers (HSTS, CSP-style, fine-grained Cache-Control) |
| `_redirects` | Cloudflare Pages — vanity path redirects |
| `wrangler.toml` | Cloudflare Pages config (project name + compat date) |
| `deploy.sh` / `deploy.cmd` | One-shot `wrangler pages deploy` wrappers (Mac/Linux & Windows) |
| `robots.txt` / `sitemap.xml` | SEO |
| `.gitignore` | Excludes `*.bak`, `node_modules`, `.wrangler/` if you commit this folder |

## Quick local preview

```
cd mtf_dashboard_v4
python -m http.server 8080
# open http://127.0.0.1:8080
```

A real HTTP server is required (`fetch` + `DecompressionStream` don't work over `file://`).

## Deploy to Cloudflare Pages

**One command** (after `wrangler login`):

```bash
./deploy.sh           # Mac / Linux
deploy.cmd            # Windows
```

Or drag-and-drop the folder onto the Cloudflare Pages dashboard. Full instructions including custom-domain setup, GitHub integration, and rollbacks: see [`DEPLOYMENT.md`](./DEPLOYMENT.md).

## Data refresh cycle

1. Run the downloader (`mtf_downloader.py`, with BSE URL patched in the parent project) to pull new BSE/NSE MTF reports.
2. Re-run the extractor (`extract_daily_totals_complete_fix.py`) which writes `mtf_daily_totals_complete.json`.
3. Re-run the sanitizer (`sanitize_daily_totals.py`) → cleaned `mtf_daily_totals.json`.
4. Copy `mtf_daily_totals.json` (and, if changed, `compressed_data/` files) into this folder and redeploy.
