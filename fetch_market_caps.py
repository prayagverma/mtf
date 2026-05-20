#!/usr/bin/env python3
"""Fetch live market caps from BSE's bulk ListofScripData endpoint and
write market_caps.json keyed by ISIN.

BSE serves the full active-equity universe (≈4,850 scrips, ≈95% with a
live Mktcap) from a single first-party endpoint. Because BSE lists
essentially every Indian equity (dual-listed NSE names appear here too),
this one source covers the whole MTF universe.

The `Mktcap` field is in ₹ CRORE. We store `mcap_lakhs` (= crore × 100)
so the dashboard's fmtINR() — which expects lakhs and auto-formats to
₹ Cr / ₹ K Cr — renders it directly without a unit conversion on the
client side.

Output schema (market_caps.json):
{
  "INE002A01018": {
    "mcap_lakhs": 178940760.0,
    "scrip_code": "500325",
    "symbol_bse": "RELIANCE",
    "source": "bse_listofscripdata"
  },
  ...
}

Resilient: a fetch failure leaves any existing market_caps.json intact
(the pipeline degrades to showing '—' for mcap, never crashes).
"""

import argparse
import json
import os
import sys
import time

import requests

BSE_HOME = "https://www.bseindia.com/"
BSE_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)
OUT_PATH = "market_caps.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}


def fetch_rows(timeout=60, retries=3):
    """Return the parsed JSON list from BSE, warming up cookies first."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # Warm up — BSE sets anti-bot cookies on the homepage that
            # the api.bseindia.com host then validates.
            sess.get(BSE_HOME, timeout=timeout)
            resp = sess.get(BSE_URL, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return data
            last_err = f"unexpected payload (type={type(data).__name__}, len={len(data) if hasattr(data,'__len__') else '?'})"
        except (requests.RequestException, ValueError) as e:
            last_err = str(e)
        print(f"  attempt {attempt}/{retries} failed: {last_err}")
        time.sleep(3 * attempt)
    raise RuntimeError(f"BSE ListofScripData fetch failed: {last_err}")


def build_market_caps(rows, limit=None):
    out = {}
    skipped_no_isin = skipped_no_mcap = 0
    for r in rows:
        isin = (r.get("ISIN_NUMBER") or "").strip().upper()
        raw = r.get("Mktcap")
        if not isin:
            skipped_no_isin += 1
            continue
        if raw in (None, "", "0", "0.00"):
            skipped_no_mcap += 1
            continue
        try:
            mc_crore = float(str(raw).replace(",", "").strip())
        except ValueError:
            skipped_no_mcap += 1
            continue
        if mc_crore <= 0:
            skipped_no_mcap += 1
            continue
        # Keep the larger value if an ISIN somehow appears twice.
        mcap_lakhs = round(mc_crore * 100.0, 2)
        prev = out.get(isin)
        if prev and prev["mcap_lakhs"] >= mcap_lakhs:
            continue
        out[isin] = {
            "mcap_lakhs": mcap_lakhs,
            "scrip_code": (r.get("SCRIP_CD") or "").strip(),
            "symbol_bse": (r.get("scrip_id") or "").strip(),
            "source": "bse_listofscripdata",
        }
        if limit and len(out) >= limit:
            break
    return out, skipped_no_isin, skipped_no_mcap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_PATH, help="output JSON path")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the number of ISINs (smoke test)")
    args = ap.parse_args()

    print("Fetching BSE ListofScripData …")
    try:
        rows = fetch_rows()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        # Don't clobber an existing file on transient failure.
        if os.path.exists(args.out):
            print(f"Keeping existing {args.out} ({os.path.getsize(args.out):,} bytes).")
            return 0
        return 1

    print(f"  fetched {len(rows)} scrips")
    caps, no_isin, no_mcap = build_market_caps(rows, limit=args.limit)
    print(f"  parsed {len(caps)} ISINs with mcap "
          f"(skipped {no_isin} no-ISIN, {no_mcap} no-mcap)")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(caps, f, separators=(",", ":"))
    print(f"Wrote {args.out} ({os.path.getsize(args.out):,} bytes)")

    # Spot-check a few well-known ISINs.
    for isin, label in [("INE002A01018", "RELIANCE"),
                        ("INE467B01029", "TCS"),
                        ("INE040A01034", "HDFCBANK")]:
        rec = caps.get(isin)
        if rec:
            print(f"  {label:10} {isin}: ₹{rec['mcap_lakhs']/100:,.0f} Cr")
    return 0


if __name__ == "__main__":
    sys.exit(main())
