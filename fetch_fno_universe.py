#!/usr/bin/env python3
"""Build the two universes the dashboard needs to split MTF book AUM into
F&O / non-F&O / ETF buckets:

  fno_membership.json  {"YYYY-MM": ["RELIANCE","ACC", ...], ...}
      Point-in-time F&O *stock* underlyings, one entry per calendar month
      from 2017-06 to the current month. The set of stock underlyings that
      traded in the NSE F&O bhavcopy on a date IS the F&O membership on
      that date — so a stock counts as F&O only from when it actually
      entered the segment (and drops out when it exits). This is the
      ground truth; NSE circulars are not needed (and don't go back far
      enough anyway).

  etf_list.json        {"symbols": [...], "isins": [...]}
      The NSE ETF universe from eq_etfseclist.csv. ETF-ness is static, so
      the current list applies to all history; the classifier also treats
      any ISIN starting "INF" (mutual-fund/ETF units) as an ETF backstop.

Data sources (all NSE first-party, reachable directly; browser UA only —
never log cookies):
  - F&O bhavcopy, UDiFF format (>= ~2024-07):
      content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip
      keep rows FinInstrmTp in {STF,STO}, unique TckrSymb
  - F&O bhavcopy, legacy format (< 2024-07):
      content/historical/DERIVATIVES/<YYYY>/<MON>/fo<DD><MON><YYYY>bhav.csv.zip
      keep rows INSTRUMENT in {FUTSTK,OPTSTK}, unique SYMBOL
  - Current F&O list (anchors the latest partial month):
      content/fo/NSE_FO_SosScheme.csv -> unique Symbol where Symbol Type=EQUITY
  - ETF list:
      content/equities/eq_etfseclist.csv

Incremental: months already present in fno_membership.json are immutable
and skipped; only the current month is always refreshed. The first run
backfills ~107 months (~2 min); routine runs fetch ~1 file.

Resilient: any fetch failure leaves the existing JSON intact.
"""

import csv as _csv
import io
import json
import os
import sys
import time
import zipfile
from datetime import date, datetime

import requests

ARCH = "https://nsearchives.nseindia.com"
UDIFF_URL = ARCH + "/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
LEGACY_URL = ARCH + "/content/historical/DERIVATIVES/{y}/{mon}/fo{d:02d}{mon}{y}bhav.csv.zip"
SOS_URL = ARCH + "/content/fo/NSE_FO_SosScheme.csv"
ETF_URL = ARCH + "/content/equities/eq_etfseclist.csv"

OUT_FNO = "fno_membership.json"
OUT_ETF = "etf_list.json"

START_YEAR, START_MONTH = 2017, 6
# NSE switched the F&O bhavcopy to the UDiFF layout in mid-2024. Try UDiFF
# first on/after this date, legacy first before it; the other is a fallback.
UDIFF_FROM = date(2024, 7, 1)
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/zip,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get_zip_csv(sess, url, timeout=30):
    """GET a .zip, return its single CSV member's text, or None on any miss."""
    try:
        r = sess.get(url, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.content:
        return None
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        return None
    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not names:
        return None
    return zf.read(names[0]).decode("utf-8", "replace")


def _parse_udiff(text):
    rd = _csv.DictReader(io.StringIO(text))
    return {
        (row.get("TckrSymb") or "").strip().upper()
        for row in rd
        if (row.get("FinInstrmTp") or "").strip() in ("STF", "STO")
    } - {""}


def _parse_legacy(text):
    rd = _csv.DictReader(io.StringIO(text))
    return {
        (row.get("SYMBOL") or "").strip().upper()
        for row in rd
        if (row.get("INSTRUMENT") or "").strip() in ("FUTSTK", "OPTSTK")
    } - {""}


def fno_underlyings_for_date(sess, dt):
    """Stock F&O underlyings traded on dt, or None if no bhavcopy exists."""
    ymd = dt.strftime("%Y%m%d")
    legacy = LEGACY_URL.format(y=dt.year, mon=MONTHS[dt.month - 1], d=dt.day)
    udiff = UDIFF_URL.format(ymd=ymd)
    order = ([(udiff, _parse_udiff), (legacy, _parse_legacy)]
             if dt >= UDIFF_FROM else
             [(legacy, _parse_legacy), (udiff, _parse_udiff)])
    for url, parse in order:
        text = _get_zip_csv(sess, url)
        if text:
            syms = parse(text)
            if syms:
                return syms
    return None


def fno_for_month(sess, y, m):
    """First available trading day's underlyings for month (y, m). Tries the
    first ~10 calendar days so weekends/holidays at month start are skipped."""
    for day in range(1, 11):
        try:
            dt = date(y, m, day)
        except ValueError:
            break
        syms = fno_underlyings_for_date(sess, dt)
        if syms:
            return sorted(syms), day
        time.sleep(0.15)
    return None, None


def current_sos_equity(sess):
    """Current F&O EQUITY underlyings from NSE_FO_SosScheme.csv (or empty)."""
    try:
        r = sess.get(SOS_URL, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  SOS scheme fetch failed: {e}")
        return set()
    lines = r.text.splitlines()
    # First line is a date stamp (e.g. "20052026"); the header follows.
    start = 1 if lines and "," not in lines[0] else 0
    rd = _csv.DictReader(lines[start:])
    return {
        (row.get("Symbol") or "").strip().upper()
        for row in rd
        if (row.get("Symbol Type") or "").strip().upper() == "EQUITY"
    } - {""}


def month_keys(end_y, end_m):
    y, m = START_YEAR, START_MONTH
    out = []
    while (y, m) <= (end_y, end_m):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def build_fno_membership(sess, out_path=OUT_FNO):
    existing = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    today = datetime.now()
    cur_key = f"{today.year:04d}-{today.month:02d}"
    keys = month_keys(today.year, today.month)

    membership = dict(existing)
    fetched = skipped = failed = 0
    for key in keys:
        # Past months are immutable once captured; only refresh the current one.
        if key in existing and key != cur_key and existing[key]:
            skipped += 1
            continue
        y, m = int(key[:4]), int(key[5:7])
        syms, day = fno_for_month(sess, y, m)
        if syms:
            membership[key] = syms
            fetched += 1
            print(f"  {key}: {len(syms)} F&O stocks (day {day:02d})")
        else:
            failed += 1
            print(f"  {key}: no bhavcopy found (kept {'prior' if key in membership else 'none'})")

    # Anchor the current month with the live SOS scheme list (union), so the
    # latest partial month reflects today's exact membership.
    sos = current_sos_equity(sess)
    if sos:
        prior = set(membership.get(cur_key, []))
        membership[cur_key] = sorted(prior | sos)
        print(f"  {cur_key}: anchored with SOS scheme -> {len(membership[cur_key])} F&O stocks")

    if not membership:
        print("ERROR: no F&O membership built; leaving existing file untouched.")
        return False

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(membership, f, separators=(",", ":"), sort_keys=True)
    print(f"Wrote {out_path}: {len(membership)} months "
          f"({fetched} fetched, {skipped} cached, {failed} missing), "
          f"{os.path.getsize(out_path):,} bytes")
    return True


def build_etf_list(sess, out_path=OUT_ETF):
    try:
        r = sess.get(ETF_URL, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"ETF list fetch failed: {e}")
        if os.path.exists(out_path):
            print(f"Keeping existing {out_path}.")
        return False
    rd = _csv.DictReader(io.StringIO(r.text))
    symbols, isins = set(), set()
    for row in rd:
        sym = (row.get("Symbol") or "").strip().upper()
        isin = (row.get("ISINNumber") or row.get("ISIN") or "").strip().upper()
        if sym:
            symbols.add(sym)
        if isin:
            isins.add(isin)
    if not symbols:
        print("ERROR: ETF list parsed empty; leaving existing file untouched.")
        return False
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"symbols": sorted(symbols), "isins": sorted(isins)},
                  f, separators=(",", ":"))
    print(f"Wrote {out_path}: {len(symbols)} ETF symbols, {len(isins)} ISINs")
    return True


def main():
    sess = _session()
    print("Building ETF universe (eq_etfseclist.csv) …")
    build_etf_list(sess)
    print("Building point-in-time F&O membership (monthly bhavcopy) …")
    build_fno_membership(sess)
    return 0


if __name__ == "__main__":
    sys.exit(main())
