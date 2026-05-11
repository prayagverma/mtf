# Cloudflare Pages — Deployment Guide

This folder is shaped specifically for **Cloudflare Pages**. Pick whichever path fits your workflow.

> **Looking to automate daily refresh + deploy?** See [`/.github/workflows/README.md`](../.github/workflows/README.md) — it wires up a daily GitHub Actions job that fetches new BSE/NSE reports, regenerates all derived data, and ships to Pages.

---

## Option 1 — `wrangler` CLI (recommended)

One-time setup:

```bash
npm install -g wrangler
wrangler login        # opens a browser, authorises wrangler
```

Deploy from this folder:

```bash
./deploy.sh                        # Mac / Linux
deploy.cmd                         # Windows
# or directly:
wrangler pages deploy . --project-name mtf
```

Wrangler will:

1. Create the Pages project on first run (you'll see a prompt to confirm).
2. Upload everything in this folder.
3. Print the deploy URL: `https://mtf.pages.dev` (and a per-deploy alias).

Subsequent runs deploy to the same project. Use `--branch <name>` to push to a preview branch instead of production:

```bash
./deploy.sh --branch staging
```

---

## Option 2 — Drag-and-drop (no CLI needed)

1. https://dash.cloudflare.com/?to=/:account/pages
2. **Create a project** → **Direct upload**.
3. Drag this `mtf_dashboard_v4/` folder into the upload zone.
4. Set the project name (e.g. `mtf`) and click **Deploy site**.

Both `_headers` and `_redirects` are picked up automatically.

---

## Option 3 — GitHub integration

Useful for auto-deploys on push.

1. Push this folder to a GitHub repo (it can live at the root, or as a subfolder).
2. Cloudflare dashboard → **Pages** → **Create a project** → **Connect to Git** → pick the repo.
3. Build settings:
   - **Framework preset**: *None*
   - **Build command**: *(leave empty)*
   - **Build output directory**: `.` (or `mtf_dashboard_v4` if hosted in a subfolder of a larger repo)
   - **Root directory**: same as above

Every push to the production branch auto-deploys. PRs get preview URLs.

---

## Custom domain

After the first deploy:

1. Pages project → **Custom domains** → **Set up a custom domain**.
2. Add `mtf.example.com` and follow the CNAME instructions Cloudflare shows.
3. The HSTS header in `_headers` (`max-age=63072000; includeSubDomains; preload`) is opt-in only after HTTPS is fully wired across all your subdomains. Remove it from `_headers` first if you're not ready, then redeploy.

---

## Verifying the deployment

After deploying, sanity-check:

- [ ] `https://your-domain/` loads and the chart renders within ~3 seconds
- [ ] DevTools console is free of CDN failures (Oat 0.6.1, lightweight-charts 5.2.0, Google Fonts)
- [ ] **Both Exchanges** view shows two distinct lines (NSE blue, BSE green)
- [ ] Cross-Exchange tab populates (computed on-the-fly from `stock_index`)
- [ ] Dark mode toggle persists across reloads (localStorage `mtf-theme`)
- [ ] `https://your-domain/non-existent` shows the branded 404 page
- [ ] `curl -sI https://your-domain/mtf_daily_totals.json | grep -i cache-control`
      → `Cache-Control: public, max-age=600, s-maxage=3600`
- [ ] `curl -sI https://your-domain/compressed_data/stock_analytics_base.json.gz | grep -i content-encoding`
      → `Content-Encoding: gzip`
- [ ] Lighthouse Performance > 95, Accessibility > 95, Best Practices > 95

---

## Rolling back

Cloudflare Pages keeps every deployment.

```bash
wrangler pages deployment list --project-name mtf
wrangler pages deployment activate <DEPLOYMENT_ID> --project-name mtf
```

Or via the dashboard: **Deployments → ⋯ → Rollback to this deployment**.

---

## Updating the data

The dashboard reads `mtf_daily_totals.json` from the deploy root. To ship fresh data:

1. In the parent project run `mtf_downloader.py` → `extract_daily_totals_complete_fix.py` → `sanitize_daily_totals.py`.
2. Copy the resulting cleaned `mtf_daily_totals.json` into this folder, overwriting the existing file.
3. `./deploy.sh` (or your chosen path).

If per-stock data changes (rare — needs the original 600 MB `stock_analytics.json` source), regenerate `compressed_data/` via `compress_stock_data.py` first.

---

## Troubleshooting

**Q: Cloudflare returns my pages but `_headers` rules don't seem to apply.**
A: `_headers` only takes effect after the first successful Pages deploy. Inspect `https://your-domain/_headers` — it should 404 (Pages strips it from the deployed assets but applies its rules).

**Q: Browser fetches `*.json.gz` and parses raw bytes instead of decompressing.**
A: Confirm `Content-Encoding: gzip` is in the response headers. If missing, your `_headers` file isn't being picked up — verify it's at the deploy root with no BOM.

**Q: Custom domain shows a Cloudflare error page.**
A: Wait 1–2 min after adding the CNAME. If it persists, check **DNS** tab → confirm a CNAME (orange-clouded) pointing at `<project>.pages.dev`.
