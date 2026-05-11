# GitHub Actions: MTF data refresh + deploy

This repo has a single workflow at [`refresh-and-deploy.yml`](./refresh-and-deploy.yml) that runs the full pipeline daily.

## What it does

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Checkout repo                                             │
│ 2. setup-python 3.12 + pip install -r requirements.txt       │
│ 3. mtf_downloader.py --last-days 7   (fetches new reports)   │
│ 4. extract_daily_totals_complete_fix.py                      │
│ 5. sanitize_daily_totals.py                                  │
│ 6. trim to dates >= 2017-06-22                               │
│ 7. extract_stock_data.py             (~5 min, ~1.7 GB JSON)  │
│ 8. compress_stock_data.py            (→ 5 gzipped chunks)    │
│ 9. sync mtf_daily_totals.json + compressed_data/ → v4/       │
│10. cloudflare/wrangler-action@v3 → pages deploy              │
│11. git commit + push (raw reports + derived files)           │
└──────────────────────────────────────────────────────────────┘
```

Runtime: ~10–15 min per run.

## When it runs

- **Daily at 22:00 IST, Mon–Fri** (`cron: 30 16 * * 1-5` UTC)
- **Manual trigger** from the Actions tab — supports overrides:
  - `lookback_days` (default `7`) — how many trailing days to fetch
  - `skip_deploy` — extract + commit only, skip the Cloudflare deploy
  - `skip_commit` — deploy only, don't commit refreshed data back to git

## One-time setup (required before the first run)

The workflow needs two secrets in **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Where to get it |
|---|---|
| `CLOUDFLARE_API_TOKEN` | https://dash.cloudflare.com/profile/api-tokens → **Create Token** → use the **"Edit Cloudflare Workers"** template (or a custom token with **Account → Cloudflare Pages → Edit** permission). |
| `CLOUDFLARE_ACCOUNT_ID` | Any Cloudflare dashboard page → the URL is `https://dash.cloudflare.com/<ACCOUNT_ID>/...` |

The Cloudflare Pages project must already exist (run the first deploy manually via `./deploy.sh` from `mtf_dashboard_v4/`, or use Direct Upload from the dashboard).

No additional secret is needed for `git push` — the workflow uses the default `GITHUB_TOKEN` and `permissions: contents: write` in the workflow YAML.

## Manual first run

After setting the two secrets above:

1. Go to **Actions → Refresh MTF data & deploy → Run workflow**
2. Tweak the inputs if you like (default `lookback_days: 7` is fine)
3. Click **Run workflow**

The first run will:
- Download up to 7 days of new BSE/NSE reports (most likely no-ops if your repo is already up to date)
- Re-run extraction + compression on the full historical dataset (~10 min for the stock extractor)
- Deploy to Cloudflare Pages
- Commit the new files back to `main`

## Expected commit growth

Each successful run commits, on average:

| Bucket | Size per run |
|---|---:|
| `mtf_reports/BSE/*.xls` or `*.csv` | ~80 KB/day (1 file) |
| `mtf_reports/NSE/*.zip` | ~40 KB/day (1 file) |
| `mtf_daily_totals.json` + variants | replaces (~900 KB total, but content differs by ~1 row × 7) |
| `mtf_dashboard_v4/compressed_data/*.json.gz` | **replaces all 5 chunks, ~40 MB** |
| `compressed_data/*.json.gz` | same set, mirror |

The compressed_data files are the bulk — they're regenerated from scratch each run, so git stores a fresh blob each time. Plan for ~1–2 GB of repo growth per year of daily runs. If this becomes a problem:

- **Option A**: use [Git LFS](https://git-lfs.com) for `compressed_data/**` and `mtf_dashboard_v4/compressed_data/**`
- **Option B**: stop committing `compressed_data/` and rely on Cloudflare Pages deployment history instead — flip `skip_commit: true` on scheduled runs OR remove those paths from the `git add` list in `refresh-and-deploy.yml`

## Failure modes & retries

The workflow has `concurrency: cancel-in-progress: false`, so the next scheduled run won't stomp on a still-running one.

| Failure | What happens |
|---|---|
| Cloudflare API token wrong | Deploy step fails → no commit happens (workflow stops at step 10). Re-run after fixing the secret. |
| BSE/NSE 403 on a single file | `mtf_downloader.py` logs and continues; next run picks it up via `--last-days 7`. |
| Public holiday (no report) | Downloader gets 404, treats as "no report for date X", continues. No action needed. |
| BSE format change (e.g. another schema flip) | `extract_*` scripts will start emitting `0` rows or wrong values. Job summary will show suspicious counts. Fix locally, push the script update, the next run picks it up. |

## Debugging locally

Reproduce the full pipeline on your laptop:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python mtf_downloader.py --last-days 7 --exchange both --delay 2
python extract_daily_totals_complete_fix.py
python sanitize_daily_totals.py --no-backup
# (run the trim Python snippet from the workflow yaml)
python extract_stock_data.py
python compress_stock_data.py

# sync + deploy
cp mtf_daily_totals.json mtf_dashboard_v4/
rm -f mtf_dashboard_v4/compressed_data/*.json.gz
cp compressed_data/*.json.gz compressed_data/manifest.json mtf_dashboard_v4/compressed_data/
cd mtf_dashboard_v4 && ./deploy.sh
```

## Why no caching?

Earlier drafts of this workflow used `actions/cache` for `mtf_reports/` to avoid committing raw reports. We switched to committing everything per the project's preference for full audit trail in git. If you prefer cache-only:

1. Add `actions/cache/restore` before step 3 and `actions/cache/save` after, keyed by `mtf-reports-${{ github.run_id }}` with restore-key `mtf-reports-`.
2. Remove `mtf_reports/` from the `git add` list in the commit step.
