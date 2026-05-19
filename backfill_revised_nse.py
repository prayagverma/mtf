#!/usr/bin/env python3
"""
backfill_revised_nse.py — one-shot rescue of NSE dates where our archive
holds a partial / provisional report. Re-fetches each candidate date
from NSE and compares to the local copy.

Two failure modes are addressed:

  1. EXPLICIT — line 1 of the NSE CSV says
     "Please note the figures are provisional as few members have not
      submitted the data".
     50 such dates from 2021-11-06 through 2025-06-05.

  2. IMPLICIT — no disclaimer line, but the day's end_outstanding dips
     >=10% below the average of yesterday + tomorrow while yesterday
     and tomorrow are within 5% of each other ("spike-island").
     12 such dates from 2017-08-16 through 2023-06-20.

For each candidate, the script:

  * Backs up the existing zip to mtf_reports/NSE/_provisional_backup/
  * Forces a re-fetch via the existing MTFDownloader.download_nse_report()
  * Diffs the new file against the backup (header markers + end_outstanding)
  * Categorises as REVISED / SAME / FETCH_FAILED / MISSING_ORIG

Run modes:
  python backfill_revised_nse.py --dry-run        # print plan, do nothing
  python backfill_revised_nse.py                  # back up + re-fetch + report

Output: backfill_revised_nse_report.csv

This script is NOT part of CI. Run it once locally, review the CSV,
commit the improved zips (and any backed-up originals) explicitly.
"""

import argparse
import csv
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import date, datetime

from mtf_downloader import MTFDownloader


# ──────────────────────────────────────────────────────────────────────
# Candidate date lists. Pre-2017 entries excluded — dashboard trims
# the time series to >= 2017-06-22.
# ──────────────────────────────────────────────────────────────────────

PROVISIONAL_DATES = [
    "2021-11-06", "2021-11-23", "2021-11-24", "2021-11-25", "2021-12-08",
    "2021-12-16", "2022-01-19", "2022-01-24", "2022-01-25", "2022-01-27",
    "2022-02-03", "2022-02-04", "2022-02-07", "2022-02-08", "2022-03-11",
    "2022-04-05", "2022-04-06", "2022-04-07", "2022-05-05", "2022-06-02",
    "2022-06-08", "2022-07-01", "2022-08-04", "2022-08-12", "2022-08-30",
    "2022-09-01", "2022-09-06", "2022-09-13", "2022-09-29", "2022-10-14",
    "2022-10-21", "2022-10-25", "2022-11-02", "2022-12-02", "2022-12-07",
    "2022-12-12", "2022-12-16", "2022-12-29", "2023-01-13", "2023-02-27",
    "2023-03-06", "2023-03-27", "2023-03-31", "2023-06-02", "2023-06-22",
    "2024-12-26", "2025-03-06", "2025-05-21", "2025-06-05",
]

SPIKE_ISLAND_DATES = [
    "2017-08-16", "2017-08-30", "2017-09-06", "2017-10-13", "2017-10-18",
    "2022-02-25", "2022-03-25", "2022-05-12", "2022-06-21", "2022-11-18",
    "2023-02-02", "2023-06-20",
]

ALL_CANDIDATES = sorted(set(PROVISIONAL_DATES + SPIKE_ISLAND_DATES))

NSE_DIR = os.path.join("mtf_reports", "NSE")
BACKUP_DIR = os.path.join(NSE_DIR, "_provisional_backup")
REPORT_PATH = "backfill_revised_nse_report.csv"


def _zip_path(d: date) -> str:
    return os.path.join(NSE_DIR, f"NSE_MTF_{d.strftime('%d%m%Y')}.zip")


def _read_zip_summary(path: str) -> dict:
    """Return {has_provisional, has_dual_block, end_outstanding, size}
    for the given NSE zip. Missing file → all keys None / 0."""
    if not os.path.exists(path):
        return {"has_provisional": None, "has_dual_block": None,
                "end_outstanding": None, "size": 0}
    try:
        with zipfile.ZipFile(path, "r") as z:
            csvs = [n for n in z.namelist() if n.endswith(".csv")]
            if not csvs:
                return {"has_provisional": None, "has_dual_block": None,
                        "end_outstanding": None, "size": os.path.getsize(path)}
            content = z.read(csvs[0]).decode("utf-8", "ignore")
    except (zipfile.BadZipFile, OSError):
        return {"has_provisional": None, "has_dual_block": None,
                "end_outstanding": None, "size": os.path.getsize(path)}

    head = content[:4000].lower()
    has_dual = "for reporting date" in head
    has_prov = "provisional" in head

    # Pull rightmost numeric > 1000 on the 'outstanding at the end' line
    # (matches the extractor's "last numeric wins" logic for dual blocks).
    end_val = None
    for line in content.split("\n")[:30]:
        if "outstanding at the end" in line:
            for part in line.split(","):
                cleaned = re.sub(r"[^\d.-]", "", part.strip())
                if cleaned and "." in cleaned:
                    try:
                        v = float(cleaned)
                        if v > 1000:
                            end_val = v   # keep walking → last wins
                    except ValueError:
                        continue
            break

    return {
        "has_provisional": has_prov,
        "has_dual_block": has_dual,
        "end_outstanding": end_val,
        "size": os.path.getsize(path),
    }


def _classify(orig: dict, new: dict) -> str:
    """Decide REVISED / SAME / FETCH_FAILED / MISSING_ORIG based on the
    pre / post zip summaries. REVISED means the new file carries the
    final / dual-block data we wanted."""
    if orig["size"] == 0:
        return "MISSING_ORIG"
    if new["size"] == 0:
        return "FETCH_FAILED"
    if new["has_dual_block"] and not orig["has_dual_block"]:
        return "REVISED"     # final block now present
    if (orig["has_provisional"] and not new["has_provisional"]
            and (new["end_outstanding"] or 0) > (orig["end_outstanding"] or 0)):
        return "REVISED"     # disclaimer dropped + value bumped up
    if (orig["end_outstanding"] and new["end_outstanding"]
            and abs(new["end_outstanding"] - orig["end_outstanding"]) / orig["end_outstanding"] > 0.005):
        return "REVISED"     # value changed by > 0.5%
    return "SAME"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print intended actions, fetch nothing")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="seconds between NSE fetches (default 3)")
    parser.add_argument("--dates", nargs="+", default=None,
                        help="explicit ISO dates to re-fetch (default = all 61 candidates)")
    args = parser.parse_args()

    candidates = args.dates if args.dates else ALL_CANDIDATES
    candidates = sorted(set(candidates))
    print(f"Backfill candidates: {len(candidates)} dates")

    if args.dry_run:
        for d in candidates:
            print(f"  would re-fetch {d}")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)

    downloader = MTFDownloader(output_dir="mtf_reports", delay=args.delay)
    if not downloader.visit_base_site("NSE"):
        print("ERROR: could not warm up NSE session — aborting.")
        return 1

    rows = []
    for iso in candidates:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        zip_path = _zip_path(d)
        backup_path = os.path.join(BACKUP_DIR, os.path.basename(zip_path))

        orig = _read_zip_summary(zip_path)

        # Back up + remove existing so download_nse_report() doesn't skip
        if os.path.exists(zip_path):
            shutil.copy2(zip_path, backup_path)
            os.remove(zip_path)

        ok = False
        try:
            ok = downloader.download_nse_report(d)
        except Exception as e:
            print(f"  ERROR fetching {iso}: {e}")
            ok = False

        # If the download failed, restore the backup so we don't lose data
        if not ok and os.path.exists(backup_path) and not os.path.exists(zip_path):
            shutil.copy2(backup_path, zip_path)

        new = _read_zip_summary(zip_path)
        verdict = _classify(orig, new)

        rows.append({
            "date": iso,
            "verdict": verdict,
            "orig_provisional": orig["has_provisional"],
            "orig_dual_block": orig["has_dual_block"],
            "orig_end_outstanding": orig["end_outstanding"],
            "new_provisional": new["has_provisional"],
            "new_dual_block": new["has_dual_block"],
            "new_end_outstanding": new["end_outstanding"],
            "diff_lakhs": ((new["end_outstanding"] or 0) - (orig["end_outstanding"] or 0))
                          if (orig["end_outstanding"] and new["end_outstanding"]) else None,
        })

        old_end = orig["end_outstanding"] or 0
        new_end = new["end_outstanding"] or 0
        print(f"  {iso}  {verdict:<13}  orig_end={old_end:>14,.2f}  new_end={new_end:>14,.2f}")
        time.sleep(args.delay)

    # Write CSV report
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    revised = sum(1 for r in rows if r["verdict"] == "REVISED")
    same = sum(1 for r in rows if r["verdict"] == "SAME")
    failed = sum(1 for r in rows if r["verdict"] == "FETCH_FAILED")
    missing = sum(1 for r in rows if r["verdict"] == "MISSING_ORIG")
    print()
    print(f"Summary: REVISED={revised}  SAME={same}  FETCH_FAILED={failed}  MISSING_ORIG={missing}")
    print(f"Report:  {REPORT_PATH}")
    print(f"Backups: {BACKUP_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
