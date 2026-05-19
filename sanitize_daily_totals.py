#!/usr/bin/env python3
"""
Drop transient single-day glitches (e.g. BSE 2025-09-30 partial-publication row)
from the daily totals JSON files served by the dashboard.

Logic mirrors the chart-side _sanitizeSeries():
  - Drop any row whose end_outstanding is non-positive.
  - Drop any row whose end_outstanding is < 40% of the median of an 8-day
    surrounding window OR < 50% of the minimum of its immediate neighbours.
  - Iterated up to 3 passes to catch clustered glitches.
Real regime shifts (a step-down that doesn't recover) are preserved.

Writes cleaned outputs back to the same paths and produces a CSV+crores variant.
"""
import argparse
import csv
import json
import os
import shutil
import statistics
from datetime import datetime
from typing import Dict, List


def _spike_island_pass(rows: List[dict]) -> tuple[List[dict], List[dict]]:
    """Drop undisclaimered single-day partial-report dips.

    A row is dropped iff its end_outstanding sits >=10% below the
    average of the immediately-adjacent trading days AND those two
    neighbours are within 5% of each other. Real market shocks
    take several days to recover, so prev/next can't be that
    close to each other unless today is the outlier.

    Targets the 18-Nov-2022 family (~13 historical dates where NSE
    published a partial report with no 'provisional' header).
    """
    if len(rows) < 3:
        return list(rows), []
    kept = [rows[0]]
    dropped: List[dict] = []
    for i in range(1, len(rows) - 1):
        r = rows[i]
        v = r.get('end_outstanding') or 0
        prev_v = rows[i - 1].get('end_outstanding') or 0
        next_v = rows[i + 1].get('end_outstanding') or 0
        if v <= 0 or prev_v <= 0 or next_v <= 0:
            kept.append(r); continue
        avg_n = (prev_v + next_v) / 2.0
        if avg_n <= 0:
            kept.append(r); continue
        dip = (v - avg_n) / avg_n               # < 0 for a dip
        gap = abs(prev_v - next_v) / prev_v     # neighbour spread
        if dip < -0.10 and gap < 0.05:
            dropped.append(r); continue
        kept.append(r)
    kept.append(rows[-1])
    return kept, dropped


def sanitize_series(rows: List[dict]) -> tuple[List[dict], List[dict]]:
    """Return (kept_rows, dropped_rows). Operates on a single-exchange list sorted by date."""
    cur = [r for r in rows if (r.get('end_outstanding') or 0) > 0]
    dropped: List[dict] = [r for r in rows if r not in cur]

    win = 4
    for _ in range(3):
        out: List[dict] = []
        removed = 0
        for i, r in enumerate(cur):
            v = r.get('end_outstanding') or 0
            lo, hi = max(0, i - win), min(len(cur) - 1, i + win)
            ns = [cur[j].get('end_outstanding') or 0 for j in range(lo, hi + 1) if j != i]
            if len(ns) < 2:
                out.append(r); continue
            med = statistics.median(ns)
            prev_v = cur[i - 1].get('end_outstanding') if i > 0 else None
            next_v = cur[i + 1].get('end_outstanding') if i < len(cur) - 1 else None
            min_n = (
                min(prev_v, next_v) if (prev_v is not None and next_v is not None)
                else (prev_v if prev_v is not None else next_v)
            )
            if med >= 100 and v < 0.4 * med:
                dropped.append(r); removed += 1; continue
            if min_n is not None and min_n >= 100 and v < 0.5 * min_n:
                dropped.append(r); removed += 1; continue
            out.append(r)
        cur = out
        if not removed:
            break

    # Second pass: spike-island filter (~13 NSE dates without
    # explicit provisional disclaimer that exhibit the same dip-
    # then-recover signature).
    cur, more_dropped = _spike_island_pass(cur)
    dropped.extend(more_dropped)
    return cur, dropped


def sanitize_long(rows: List[dict]) -> tuple[List[dict], List[dict]]:
    """Sanitize a long-format list (one row per (date, exchange))."""
    by_ex: Dict[str, List[dict]] = {}
    for r in rows:
        ex = (r.get('exchange') or '').upper()
        by_ex.setdefault(ex, []).append(r)

    kept: List[dict] = []
    dropped: List[dict] = []
    for ex, lst in by_ex.items():
        lst_sorted = sorted(lst, key=lambda r: r.get('date', ''))
        k, d = sanitize_series(lst_sorted)
        kept.extend(k); dropped.extend(d)

    kept.sort(key=lambda r: (r.get('date', ''), r.get('exchange', '')))
    return kept, dropped


def write_csv(rows: List[dict], path: str) -> None:
    if not rows:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('')
        return
    fields = list(rows[0].keys())
    extra = []
    for r in rows:
        for k in r:
            if k not in fields and k not in extra:
                extra.append(k)
    fields = fields + extra
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def to_crores(rows: List[dict]) -> List[dict]:
    monetary = {
        'beginning_outstanding', 'fresh_exposure', 'exposure_liquidated',
        'end_outstanding', 'amount_financed', 'exposure_taken',
    }
    out = []
    for r in rows:
        new = {}
        for k, v in r.items():
            if k in monetary and isinstance(v, (int, float)):
                new[k] = round(v / 100.0, 2)
            else:
                new[k] = v
        out.append(new)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', default='mtf_daily_totals_complete.json',
                    help='Source long-format JSON (default: mtf_daily_totals_complete.json)')
    ap.add_argument('--write-canonical', action='store_true', default=True,
                    help='Also overwrite mtf_daily_totals.json (the website default fetch)')
    ap.add_argument('--no-canonical', dest='write_canonical', action='store_false')
    ap.add_argument('--backup', action='store_true', default=True,
                    help='Save .bak copies of any file we overwrite')
    ap.add_argument('--no-backup', dest='backup', action='store_false')
    args = ap.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(f'Input not found: {args.input}')

    with open(args.input, encoding='utf-8') as f:
        raw = json.load(f)
    print(f'Loaded {len(raw)} rows from {args.input}')

    kept, dropped = sanitize_long(raw)
    by_ex = {}
    for r in dropped:
        by_ex.setdefault(r.get('exchange', '?'), []).append(r)

    print(f'Sanitized: kept={len(kept)} dropped={len(dropped)}')
    for ex, lst in sorted(by_ex.items()):
        print(f'  {ex}: {len(lst)} rows dropped')
        for r in sorted(lst, key=lambda x: x.get('date', '')):
            print(f"    {r.get('date')} end_outstanding={r.get('end_outstanding')} "
                  f"securities_count={r.get('securities_count')}")

    def overwrite(dst: str, content_writer) -> None:
        if args.backup and os.path.exists(dst):
            bak = dst + '.bak'
            if not os.path.exists(bak):
                shutil.copy2(dst, bak)
                print(f'  backed up: {dst} -> {bak}')
        content_writer(dst)
        print(f'  wrote: {dst} ({os.path.getsize(dst):,} bytes)')

    print('Writing JSON outputs...')
    overwrite(args.input, lambda p: json.dump(kept, open(p, 'w', encoding='utf-8'), indent=2))

    if args.write_canonical:
        canonical = 'mtf_daily_totals.json'
        overwrite(canonical, lambda p: json.dump(kept, open(p, 'w', encoding='utf-8'), indent=2))

    print('Writing CSV outputs...')
    csv_complete = 'mtf_daily_totals_complete.csv'
    overwrite(csv_complete, lambda p: write_csv(kept, p))
    csv_canonical = 'mtf_daily_totals.csv'
    overwrite(csv_canonical, lambda p: write_csv(kept, p))

    print('Writing crores variants...')
    cr = to_crores(kept)
    overwrite('mtf_daily_totals_complete_crores.csv', lambda p: write_csv(cr, p))
    overwrite('mtf_daily_totals_crores.csv', lambda p: write_csv(cr, p))
    overwrite('mtf_daily_totals_crores.json', lambda p: json.dump(cr, open(p, 'w', encoding='utf-8'), indent=2))

    print(f'\nDone. Latest date kept: {max(r.get("date","") for r in kept)}')


if __name__ == '__main__':
    main()
