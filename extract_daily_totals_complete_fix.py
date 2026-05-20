#!/usr/bin/env python3
import os
import csv as _csv
import pandas as pd
import zipfile
from datetime import datetime
import json
import re

def extract_value_from_line(line, search_term):
    """Extract numeric value from a line containing the search term.

    Returns the RIGHTMOST (last) numeric value > 1000 on the line so
    that NSE "dual-block" reports — where both PROVISIONAL (left
    columns) and FINAL (right columns) figures are stamped on the
    same physical row — yield the FINAL number rather than the stale
    provisional one. Example: on 01-SEP-2025 the NSE CSV has

        ,1,Outstanding…,7853857.57,,,,1,Outstanding…,9377865.90

    where 7,853,857.57 is the provisional figure that was later
    revised up to 9,377,865.90. Picking the last numeric on the
    line works correctly for both single-block (one value per line,
    so last == first) and dual-block (last = revised/final) files.
    """
    if search_term not in line:
        return None

    last_value = None
    for part in line.split(','):
        cleaned = re.sub(r'[^\d.-]', '', part.strip())
        if cleaned and '.' in cleaned:
            try:
                value = float(cleaned)
                # MTF values are typically large (in lakhs); skip
                # the Sr.No. column ("1", "2", "3", "4") and similar.
                if value > 1000:
                    last_value = value
            except ValueError:
                continue
    return last_value

def _null_nse_totals(date):
    return {
        'date': date.strftime('%Y-%m-%d'),
        'exchange': 'NSE',
        'beginning_outstanding': None,
        'fresh_exposure': None,
        'exposure_liquidated': None,
        'end_outstanding': None,
        'securities_count': 0
    }


def _pick_nse_csv_for_date(zip_obj, date):
    """Pick the best inner CSV in a NSE zip for the given target date.

    Some legacy NSE zips contain multiple CSVs — e.g. a `final_DDMMYYYY`
    for the previous day alongside the current day's `provisional_…`.
    Picking csv_files[0] (insertion order) silently attributed
    PREVIOUS-day data to the current zip's date for 28-Feb-2023, 09-Mar-
    2023, 28-Mar-2023, and several others. This picker scores each
    candidate by:

      1. The DDMMYYYY date in its filename matching the target date.
      2. Whether the filename contains 'final' (priority 3 = revised),
         a bare date (priority 2 = regular), or 'provisional' (priority
         1 = partial).

    Highest priority wins. Returns (inner_name, label) or (None, None)
    when no CSV in the zip references the target date — in which case
    we fall through to the first available CSV for backward compat.
    """
    target_ddmm = date.strftime('%d%m%Y')
    target_yyyymmdd = date.strftime('%Y%m%d')
    csvs = [n for n in zip_obj.namelist() if n.lower().endswith('.csv')]
    if not csvs:
        return None, None
    best, best_pri = None, -1
    for c in csvs:
        base = os.path.basename(c).lower()
        if target_ddmm not in base and target_yyyymmdd not in base:
            continue
        if 'final' in base:
            pri = 3
        elif 'provisional' in base:
            pri = 1
        else:
            pri = 2
        if pri > best_pri:
            best_pri = pri
            best = c
    if best:
        return best, ['', 'provisional', 'regular', 'final'][best_pri]
    # Backward-compat fallback: zip without date-tagged filename
    return csvs[0], 'unknown'


def _parse_nse_totals_from_content(csv_content, date):
    """Pure parser: given a NSE CSV's text content and a target date,
    return the totals dict. No file or zip I/O.

    Drops "provisional"-disclaimer-only files to null. Dual-block files
    (with both the disclaimer AND a 'for reporting date' marker) are
    kept and the rightmost numeric per metric line wins (the FINAL
    block — handled by extract_value_from_line).
    """
    head = csv_content[:4000].lower()
    is_dual_block  = 'for reporting date' in head
    is_provisional = 'provisional' in head and not is_dual_block
    if is_provisional:
        print(f"  [SKIP] {date.strftime('%Y-%m-%d')} — NSE report marked provisional, no revision available")
        return _null_nse_totals(date)

    totals = _null_nse_totals(date)
    lines = csv_content.split('\n')

    for line in lines[:30]:
        if 'Outstanding on the beginning' in line or 'Total Outstanding on the beginning' in line:
            value = extract_value_from_line(line, 'Outstanding on the beginning')
            if value and totals['beginning_outstanding'] is None:
                totals['beginning_outstanding'] = value

        elif 'Fresh Exposure taken' in line:
            value = extract_value_from_line(line, 'Fresh Exposure taken')
            if value and totals['fresh_exposure'] is None:
                totals['fresh_exposure'] = value

        elif 'Exposure liquidated' in line:
            value = extract_value_from_line(line, 'Exposure liquidated')
            if value and totals['exposure_liquidated'] is None:
                totals['exposure_liquidated'] = value

        elif 'outstanding at the end' in line or 'Net outstanding at the end' in line:
            value = extract_value_from_line(line, 'outstanding at the end')
            if value and totals['end_outstanding'] is None:
                totals['end_outstanding'] = value

    # Count UNIQUE symbols, not rows. Some NSE files list a scrip on
    # multiple rows (e.g. 01/02-Jun-2021 had 742 symbols duplicated
    # 2-3x → 2,238 rows for only 1,485 distinct symbols), which a naive
    # per-row tally inflated by ~55%.
    in_data = False
    seen_symbols = set()
    for line in lines:
        if 'Symbol,Name,Qty Fin' in line:
            in_data = True
            continue
        if in_data and line.strip():
            parts = line.split(',')
            if len(parts) >= 3:
                symbol = parts[0].strip()
                if symbol and not symbol.startswith(',') and symbol != '':
                    if 'Total' not in symbol and 'TOTAL' not in symbol:
                        if not symbol.isdigit() and len(symbol) > 0:
                            seen_symbols.add(symbol.upper())
    totals['securities_count'] = len(seen_symbols)

    return totals


def extract_nse_totals(filepath, date):
    """Extract totals from a NSE MTF zip for the given trading date.

    When the zip contains multiple CSVs (some legacy zips bundle a
    revised final-for-prev-day next to the current day's provisional),
    `_pick_nse_csv_for_date` selects the right one for `date`.
    """
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            inner, _label = _pick_nse_csv_for_date(z, date)
            if not inner:
                print(f"No CSV found in {filepath}")
                return None
            csv_content = z.read(inner).decode('utf-8', errors='ignore')
        return _parse_nse_totals_from_content(csv_content, date)
    except Exception as e:
        print(f"Error processing NSE file {filepath}: {e}")
        return None


def extract_nse_embedded_finals(filepath, zip_date):
    """Yield (other_date_iso, totals) for each `final_DDMMYYYY` CSV in
    the zip whose date is NOT the zip's own date. Used to rescue
    previously-dropped provisional dates whose revised final happens
    to live inside a later zip.

    Same-date CSVs (e.g. final_DDMMYYYY in the zip for that day) are
    already picked by extract_nse_totals via `_pick_nse_csv_for_date`
    and are NOT yielded here.
    """
    zip_iso = zip_date.strftime('%Y-%m-%d')
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            for inner in z.namelist():
                base = os.path.basename(inner).lower()
                if not base.endswith('.csv'):
                    continue
                if 'final' not in base:
                    continue
                m = re.search(r'final[_-]?(\d{2})(\d{2})(\d{4})', base) or \
                    re.search(r'final[_-]?(\d{4})(\d{2})(\d{2})', base) or \
                    re.search(r'(\d{2})(\d{2})(\d{4})_final', base) or \
                    re.search(r'(\d{4})(\d{2})(\d{2})_final', base)
                if not m:
                    continue
                a, b, c = m.groups()
                try:
                    if len(a) == 2:                     # DDMMYYYY
                        dd, mm, yyyy = a, b, c
                    else:                                # YYYYMMDD
                        yyyy, mm, dd = a, b, c
                    other_date = datetime(int(yyyy), int(mm), int(dd))
                except ValueError:
                    continue
                other_iso = other_date.strftime('%Y-%m-%d')
                if other_iso == zip_iso:
                    continue
                content = z.read(inner).decode('utf-8', errors='ignore')
                totals = _parse_nse_totals_from_content(content, other_date)
                yield other_iso, totals
    except Exception as e:
        print(f"Error scanning NSE file {filepath} for embedded finals: {e}")
        return

def extract_bse_totals(filepath, date):
    """Extract totals from a BSE MTF file.

    BSE has two on-disk formats:
      * Legacy (saved as .xls, dates <= 2025-10-01): tab-separated text with
        header `scrip_code\tscripname\tFinanced ... \tNO_EOD` and a `Total` row.
      * New SEBI report (.csv, dates >= 2025-10-03): starts with line
        "SEBI REPORT For Trade date DD-Mon-YYYY", a 4-row totals block, then
        a (Name, ISIN, Qty, Amount) securities table. Per-security TO_BOD/
        EL_DD/ET_DD/NO_EOD are NOT present in this format.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(200)
        if head.lstrip().startswith('SEBI REPORT'):
            return _extract_bse_new_csv(filepath, date)
        return _extract_bse_legacy_tsv(filepath, date)
    except Exception as e:
        print(f"Error processing BSE file {filepath}: {e}")
        return None


def _extract_bse_new_csv(filepath, date):
    """Parse the new SEBI-format BSE MTF CSV (dates >= 2025-10-03)."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    totals = {
        'date': date.strftime('%Y-%m-%d'),
        'exchange': 'BSE',
        'amount_financed': None,
        'beginning_outstanding': None,
        'exposure_taken': None,
        'exposure_liquidated': None,
        'end_outstanding': None,
        'securities_count': 0
    }

    # 4-row totals block. Each row is "<sr>,<particulars>,<value>,"
    summary_map = {
        1: 'beginning_outstanding',
        2: 'exposure_taken',
        3: 'exposure_liquidated',
        4: 'end_outstanding',
    }
    reader = _csv.reader(lines[:20])
    for row in reader:
        if not row or not row[0].strip().isdigit():
            continue
        sr = int(row[0].strip())
        if sr in summary_map and len(row) >= 3:
            try:
                totals[summary_map[sr]] = float(row[2].strip())
            except ValueError:
                pass

    # Securities table: BSE uses two header variants:
    #   * 4-col: Name,ISIN,Qty Fin by all the members(...),Amt Fin by all the members(...)
    #   * 5-col: Symbol,Name,Qty Fin by all the members(...),Amt Fin by all the members(...),reporting_date
    # Detect by matching "Amt Fin" / "Qty Fin" anywhere in the header row.
    in_data = False
    amt_col_idx = None
    isin_col_idx = None
    amount_total = 0.0
    # Dedup by ISIN (when present) else the first cell. The early new-
    # format BSE CSVs (e.g. 01/03-Oct-2025 transitional 5-col files)
    # listed every scrip twice, which inflated both the count (~2,932
    # rows for ~1,597 distinct scrips) and the summed amount. Counting
    # and summing unique keys fixes both.
    seen_keys = set()
    reader = _csv.reader(lines)
    for row in reader:
        if not row:
            continue
        if not in_data:
            joined = ','.join(c.strip().lower() for c in row)
            if 'amt fin' in joined and ('qty fin' in joined or 'no.of shares' in joined):
                # Header found — locate the Amt + ISIN column indexes
                for j, c in enumerate(row):
                    cl = c.strip().lower()
                    if amt_col_idx is None and 'amt fin' in cl:
                        amt_col_idx = j
                    if isin_col_idx is None and 'isin' in cl:
                        isin_col_idx = j
                in_data = True
            continue
        # Inside securities table
        first = row[0].strip()
        if not first or first.startswith('*'):
            continue
        if first.lower() == 'total':
            continue
        if amt_col_idx is None or len(row) <= amt_col_idx:
            continue
        try:
            amt = float(row[amt_col_idx].strip())
        except ValueError:
            continue
        key = (row[isin_col_idx].strip().upper()
               if isin_col_idx is not None and len(row) > isin_col_idx and row[isin_col_idx].strip()
               else first.upper())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        amount_total += amt

    totals['securities_count'] = len(seen_keys)
    totals['amount_financed'] = round(amount_total, 2) if seen_keys else None
    return totals


def _extract_bse_legacy_tsv(filepath, date):
    """Parse the legacy BSE MTF file (tab-separated, saved with .xls extension)."""
    try:
        # Read the raw file to get the total line
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        # Also read as dataframe to get row count
        df = pd.read_csv(filepath, sep='\t')
        
        # Remove any "Total" rows that might be included in the DataFrame
        df = df[df['scripname'].astype(str).str.lower() != 'total'].copy()
        df = df.dropna(subset=['scrip_code'])  # Remove any rows without scrip_code
        
        totals = {
            'date': date.strftime('%Y-%m-%d'),
            'exchange': 'BSE',
            'amount_financed': None,
            'beginning_outstanding': None,
            'exposure_taken': None,
            'exposure_liquidated': None,
            'end_outstanding': None,
            # Unique scrips (defensive — legacy files rarely duplicate,
            # but stay consistent with the NSE / new-CSV unique counts).
            'securities_count': int(df['scrip_code'].nunique())
        }
        
        # Find the total line (usually last line)
        total_line_found = False
        for line in reversed(all_lines):
            if 'Total' in line or 'TOTAL' in line:
                parts = line.strip().split('\t')
                if len(parts) >= 8:
                    try:
                        # Skip first two columns (code and name), then parse the numeric values
                        totals['amount_financed'] = float(parts[3]) if parts[3] else None
                        totals['beginning_outstanding'] = float(parts[4]) if parts[4] else None
                        totals['exposure_taken'] = float(parts[5]) if parts[5] else None
                        totals['exposure_liquidated'] = float(parts[6]) if parts[6] else None
                        totals['end_outstanding'] = float(parts[7]) if parts[7] else None
                        total_line_found = True
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If no total line found, calculate from data
        if not total_line_found:
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            if 'Financed by Members AMOUNT_FINANCED' in numeric_cols:
                totals['amount_financed'] = df['Financed by Members AMOUNT_FINANCED'].sum()
            if 'TO_BOD' in numeric_cols:
                totals['beginning_outstanding'] = df['TO_BOD'].sum()
            if 'ET_DD' in numeric_cols:
                totals['exposure_taken'] = df['ET_DD'].sum()
            if 'EL_DD' in numeric_cols:
                totals['exposure_liquidated'] = df['EL_DD'].sum()
            if 'NO_EOD' in numeric_cols:
                totals['end_outstanding'] = df['NO_EOD'].sum()
        
        return totals
        
    except Exception as e:
        print(f"Error processing BSE file {filepath}: {e}")
        return None

def main():
    """Extract daily totals from all MTF files with complete fix for all formats"""
    
    print("EXTRACTING DAILY TOTALS FROM MTF FILES (COMPLETE FIX)")
    print("=" * 80)
    
    all_totals = []

    # Process NSE files
    nse_dir = "mtf_reports/NSE"
    if os.path.exists(nse_dir):
        nse_files = sorted([f for f in os.listdir(nse_dir) if f.endswith('.zip')])
        print(f"\nProcessing {len(nse_files)} NSE files...")

        blank_count = 0
        success_count = 0
        # Cross-date rescue: some NSE zips bundle a `final_DDMMYYYY.csv`
        # for an earlier (revised) date. Collect those in a side-channel
        # and apply as patches once the primary pass finishes. First
        # encountered wins (sorted by date → patches from the EARLIEST
        # next-day zip win, matching how a human would resolve the
        # "which final is canonical?" question).
        nse_patches = {}        # iso_date -> totals dict
        patch_sources = {}      # iso_date -> source zip filename (for logging)

        for i, filename in enumerate(nse_files):
            if i % 100 == 0:
                print(f"  Processing NSE file {i+1}/{len(nse_files)}...")

            filepath = os.path.join(nse_dir, filename)
            date_str = filename.replace('NSE_MTF_', '').replace('.zip', '')

            try:
                date = datetime.strptime(date_str, '%d%m%Y')
                totals = extract_nse_totals(filepath, date)
                if totals:
                    if totals['end_outstanding'] is None:
                        blank_count += 1
                    else:
                        success_count += 1
                    all_totals.append(totals)

                # Scan for embedded finals that fix OTHER dates.
                for other_iso, patch in extract_nse_embedded_finals(filepath, date):
                    if other_iso in nse_patches:
                        continue
                    nse_patches[other_iso] = patch
                    patch_sources[other_iso] = filename
            except Exception as e:
                print(f"Error with {filename}: {e}")

        # Apply patches: any row in all_totals whose date is a key in
        # nse_patches AND whose end_outstanding is null/zero (i.e. was
        # dropped by the provisional-disclaimer guard) gets replaced by
        # the rescued final.
        patched = 0
        for idx, row in enumerate(all_totals):
            if row.get('exchange') != 'NSE':
                continue
            iso = row.get('date')
            if iso in nse_patches:
                cur = row.get('end_outstanding') or 0
                if cur <= 0:
                    all_totals[idx] = nse_patches[iso]
                    print(f"  [PATCH] {iso} ← rescued final embedded in {patch_sources[iso]} (end_outstanding={nse_patches[iso].get('end_outstanding')})")
                    patched += 1

        print(f"\n  NSE Processing Summary:")
        print(f"    Successfully extracted: {success_count}")
        print(f"    Files with blank totals: {blank_count}")
        print(f"    Embedded-final patches applied: {patched}")
    
    # Process BSE files (both legacy .xls and new .csv formats)
    bse_dir = "mtf_reports/BSE"
    if os.path.exists(bse_dir):
        bse_files = sorted([f for f in os.listdir(bse_dir)
                            if f.startswith('BSE_MTF_') and f.endswith(('.xls', '.csv'))])
        print(f"\nProcessing {len(bse_files)} BSE files...")
        bse_xls = sum(1 for f in bse_files if f.endswith('.xls'))
        bse_csv = sum(1 for f in bse_files if f.endswith('.csv'))
        print(f"  Legacy .xls: {bse_xls}, new .csv: {bse_csv}")

        bse_success = 0
        bse_failed = 0
        for i, filename in enumerate(bse_files):
            if i % 100 == 0:
                print(f"  Processing BSE file {i+1}/{len(bse_files)}...")

            filepath = os.path.join(bse_dir, filename)
            date_str = filename.replace('BSE_MTF_', '').rsplit('.', 1)[0]

            try:
                date = datetime.strptime(date_str, '%d%m%Y')
                totals = extract_bse_totals(filepath, date)
                if totals and totals.get('end_outstanding') is not None:
                    all_totals.append(totals)
                    bse_success += 1
                else:
                    bse_failed += 1
                    if totals:
                        all_totals.append(totals)
            except Exception as e:
                bse_failed += 1
                print(f"  Error with {filename}: {e}")
        print(f"\n  BSE Processing Summary:")
        print(f"    Successfully extracted: {bse_success}")
        print(f"    Files with missing/blank totals: {bse_failed}")
    
    # Sort by date and exchange
    all_totals.sort(key=lambda x: (x['date'], x['exchange']))
    
    # Save to CSV
    df = pd.DataFrame(all_totals)
    output_file = "mtf_daily_totals_complete.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n" + "=" * 80)
    print(f"EXTRACTION COMPLETE")
    print(f"Total records extracted: {len(all_totals)}")
    print(f"NSE records: {len([t for t in all_totals if t['exchange'] == 'NSE'])}")
    print(f"BSE records: {len([t for t in all_totals if t['exchange'] == 'BSE'])}")
    print(f"Output saved to: {output_file}")
    
    # Also save as JSON for easier reading
    json_output = "mtf_daily_totals_complete.json"
    with open(json_output, 'w') as f:
        json.dump(all_totals, f, indent=2)
    print(f"JSON output saved to: {json_output}")
    
    # Also create version in crores
    print("\nCreating version in crores...")
    
    # Convert to crores
    monetary_columns = [
        'beginning_outstanding',
        'fresh_exposure',
        'exposure_liquidated', 
        'end_outstanding',
        'amount_financed',
        'exposure_taken'
    ]
    
    df_crores = df.copy()
    for col in monetary_columns:
        if col in df_crores.columns:
            df_crores[col] = df_crores[col].apply(lambda x: round(x/100, 2) if pd.notna(x) else None)
    
    crores_file = "mtf_daily_totals_complete_crores.csv"
    df_crores.to_csv(crores_file, index=False)
    print(f"Crores version saved to: {crores_file}")
    
    # Show sample of the data
    print(f"\nSAMPLE DATA (first 5 records):")
    print(df.head().to_string(index=False))
    
    print(f"\nSAMPLE DATA (last 5 records):")
    print(df.tail().to_string(index=False))
    
    # Check for any remaining blanks
    nse_df = df[df['exchange'] == 'NSE']
    blank_nse = nse_df[nse_df['end_outstanding'].isna()]
    if not blank_nse.empty:
        print(f"\n[WARNING] {len(blank_nse)} NSE records still have blank end_outstanding values")
        print("These files may have corrupted or incompatible formats:")
        print(blank_nse[['date', 'securities_count']].head(10).to_string(index=False))
    else:
        print(f"\n[OK] All NSE records successfully extracted!")
    
    # Summary statistics
    print(f"\n" + "=" * 80)
    print("SUMMARY STATISTICS (in Lakhs)")
    print("=" * 80)
    
    for exchange in ['NSE', 'BSE']:
        exchange_df = df[df['exchange'] == exchange]
        valid_df = exchange_df.dropna(subset=['end_outstanding'])
        
        if not valid_df.empty:
            print(f"\n{exchange}:")
            print(f"  Valid records: {len(valid_df)} / {len(exchange_df)}")
            print(f"  Latest End Outstanding: {valid_df['end_outstanding'].iloc[-1]:,.2f} Lakhs")
            print(f"  Average End Outstanding: {valid_df['end_outstanding'].mean():,.2f} Lakhs")

if __name__ == "__main__":
    main()