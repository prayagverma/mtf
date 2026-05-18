#!/usr/bin/env python3
"""
Stock-Level MTF Data Extraction Script
Extracts individual stock data from BSE and NSE MTF files to enable stock-level analytics
"""

import csv as _csv
import io
import os
import re
import pandas as pd
import zipfile
import json
from datetime import datetime, timedelta
import logging
from collections import defaultdict

# Drop dates earlier than this — the daily-totals files were trimmed to the same cutoff.
MIN_DATE = datetime(2017, 6, 22)

# NSE's equity master (symbol -> ISIN). The MTF daily reports don't carry
# ISIN for NSE stocks, but BSE reports do — so we enrich NSE records with
# ISIN at extract time to enable cross-exchange dedup by a stable key.
NSE_EQUITY_MASTER_URL = 'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'
NSE_EQUITY_MASTER_CACHE = 'mtf_reports/NSE/_equity_master.csv'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _normalize_company_key(name: str) -> str:
    """Best-effort normalised short token from a company name.
    Mirrors StockMTFExtractor._bse_key_from_name so the NSE-name index
    and the BSE-name fallback produce identical lookups."""
    if not name:
        return ''
    n = re.sub(r'[^A-Za-z0-9 &]+', ' ', name).upper()
    n = re.sub(r'\b(LIMITED|LTD|LIMITE|PVT|PRIVATE|CORPORATION|CORP|COMPANY|INC|INCORPORATED|INDIA)\b', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return ' '.join(n.split()[:3])


def _load_nse_master():
    """Return ({SYMBOL: ISIN}, {NAME_KEY: SYMBOL}). Try a fresh fetch; fall
    back to the cached file so a one-off NSE outage doesn't break the run.
    NAME_KEY is a stable short token (see _normalize_company_key) — used
    to rescue BSE rows where the only identifier is a company name."""
    try:
        import requests
        resp = requests.get(
            NSE_EQUITY_MASTER_URL,
            headers={'User-Agent': 'Mozilla/5.0 (mtf.trading pipeline)'},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.text
        os.makedirs(os.path.dirname(NSE_EQUITY_MASTER_CACHE), exist_ok=True)
        with open(NSE_EQUITY_MASTER_CACHE, 'w', encoding='utf-8') as f:
            f.write(body)
        logger.info('Fetched fresh NSE equity master (%d bytes)', len(body))
    except Exception as e:
        logger.warning('NSE equity master fetch failed (%s); using cache.', e)
        try:
            with open(NSE_EQUITY_MASTER_CACHE, encoding='utf-8') as f:
                body = f.read()
        except FileNotFoundError:
            logger.error('No NSE equity master available — dedup will fall back to symbol keys.')
            return {}, {}
    sym_to_isin = {}
    name_to_sym = {}
    reader = _csv.reader(io.StringIO(body))
    header = next(reader, None) or []
    sym_idx  = next((i for i, c in enumerate(header) if c.strip().upper() == 'SYMBOL'), 0)
    name_idx = next((i for i, c in enumerate(header) if 'NAME' in c.strip().upper()), 1)
    isin_idx = next((i for i, c in enumerate(header) if 'ISIN' in c.strip().upper()), -1)
    if isin_idx < 0:
        logger.error('NSE master missing ISIN column.')
        return {}, {}
    for row in reader:
        if len(row) <= max(sym_idx, isin_idx, name_idx):
            continue
        sym  = row[sym_idx].strip()
        isin = row[isin_idx].strip()
        name = row[name_idx].strip() if name_idx >= 0 else ''
        if sym and isin:
            sym_to_isin[sym] = isin
        nk = _normalize_company_key(name)
        # Only set if not already present — first-seen wins, avoiding noisy
        # collisions between near-identical names.
        if sym and nk and nk not in name_to_sym:
            name_to_sym[nk] = sym
    logger.info('NSE symbol→ISIN map: %d entries; name→symbol map: %d entries',
                len(sym_to_isin), len(name_to_sym))
    return sym_to_isin, name_to_sym


def _load_nse_symbol_to_isin():
    """Backwards-compatible wrapper: return only the symbol→ISIN map."""
    return _load_nse_master()[0]


class StockMTFExtractor:
    def __init__(self):
        self.stock_data = defaultdict(list)  # {stock_symbol: [daily_records]}
        self.exchange_summary = {'NSE': {}, 'BSE': {}}
        self.nse_isin_map, self.nse_name_to_symbol = _load_nse_master()
        # Inverse map: ISIN → NSE symbol. Used to canonicalise BSE 4-col CSV rows
        # (which carry ISIN but no Symbol) back to the legacy BSE scripname for
        # dual-listed stocks — e.g. Infosys ISIN INE009A01021 resolves to "INFY",
        # matching the legacy BSE scripname, instead of being bucketed under
        # "INFOSYS" by the name-based fallback. The name→symbol map covers
        # transitional 5-col CSV rows (Sept-Oct 2025) where the Symbol column
        # carried a polluted company name ("INFOSYS LTD") and no ISIN was given.
        self.isin_to_nse_symbol = {isin: sym for sym, isin in self.nse_isin_map.items() if isin}
        # BSE legacy scripnames seen during .xls parsing (used by word-prefix and
        # 5-col-Symbol bridges to canonicalise post-2025-10 rows whose ISINs
        # aren't in the NSE master).
        self.bse_legacy_scripnames = set()
        # name_token → legacy_scripname, populated from the 3 transitional 5-col
        # CSVs (30 Sep / 1 Oct / 3 Oct 2025). Each carries both a polluted
        # Symbol (e.g. "REL INFRA") and a Name ("Reliance Infrastructure Ltd").
        # Stripping whitespace from Symbol often yields a legacy scripname or a
        # longer prefix of it (RELINFRA, MANGCHEFER, ANDREWYULC ⊃ ANDREWYU).
        self.bse_name_to_legacy = {}
        
    def extract_nse_stocks(self, filepath, date):
        """Extract individual stock data from NSE MTF file"""
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                csv_name = z.namelist()[0]
                csv_content = z.read(csv_name).decode('utf-8')
            
            lines = csv_content.split('\n')
            
            # Find the data section
            data_start = False
            stocks = []
            
            for line in lines:
                if 'Symbol,Name,Qty Fin by all the members' in line:
                    data_start = True
                    continue
                
                if data_start and line.strip() and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        try:
                            symbol = parts[0].strip()
                            name = parts[1].strip()
                            qty_financed = float(parts[2]) if parts[2] else 0
                            amount_financed = float(parts[3].strip().rstrip('\r')) if parts[3] else 0
                            
                            # Skip empty symbols, header rows, total row, and the
                            # NSE CSV footer (" * Figures are rounded to the nearest decimal.").
                            if not symbol or symbol.startswith('*') or symbol.lower() in ['symbol', 'total']:
                                continue
                            
                            stock_record = {
                                'date': date.strftime('%Y-%m-%d'),
                                'exchange': 'NSE',
                                'symbol': symbol,
                                'name': name,
                                # ISIN from the NSE equity master, blank if the
                                # symbol isn't listed (ETFs, fresh listings).
                                'isin': self.nse_isin_map.get(symbol, ''),
                                'qty_financed': qty_financed,
                                'amount_financed': amount_financed,
                                'avg_price': amount_financed / qty_financed if qty_financed > 0 else 0
                            }
                            
                            stocks.append(stock_record)
                            self.stock_data[symbol].append(stock_record)
                            
                        except (ValueError, ZeroDivisionError):
                            continue
            
            return stocks
            
        except Exception as e:
            logger.error(f"Error processing NSE file {filepath}: {e}")
            return []
    
    def extract_bse_stocks(self, filepath, date):
        """Extract individual stock data from a BSE MTF file.

        Handles three layouts:
          1) Legacy TSV (.xls): scrip_code, scripname, ..., NO_EOD  (≤ 2025-10-01)
          2) New SEBI CSV (.csv) 5-col Symbol|Name (Sept-Oct 2025)
          3) New SEBI CSV (.csv) 4-col Name|ISIN (Oct 2025 onwards)
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(200)
            if head.lstrip().startswith('SEBI REPORT'):
                return self._extract_bse_new_csv(filepath, date)
            return self._extract_bse_legacy_tsv(filepath, date)
        except Exception as e:
            logger.error(f"Error processing BSE file {filepath}: {e}")
            return []

    def _extract_bse_legacy_tsv(self, filepath, date):
        df = pd.read_csv(filepath, sep='\t')
        df = df[df['scripname'].astype(str).str.lower() != 'total'].copy()
        df = df.dropna(subset=['scrip_code'])
        stocks = []
        for _, row in df.iterrows():
            try:
                # Use the BSE scrip name as the key — short ticker-like form
                # (e.g. "TATAMOT", "ABB"). This matches the new CSV "Symbol" column
                # so legacy + new records merge into the same time series per stock.
                #
                # BSE flags certain trading days (ex-dividend, ex-bonus, ex-rights,
                # special segment, etc.) with a trailing '*' on the scripname —
                # e.g. "INFY*" instead of "INFY" — but the scrip code is the same
                # security. Strip the marker so both notations collapse into one
                # time series per stock (63 BSE stocks affected, 3,539 row-day
                # occurrences across the archive).
                raw_name = str(row['scripname']).strip()
                name = raw_name.rstrip('*').strip()
                key = name.upper()
                qty_financed = float(row.get('Financed by Members QUANTITY_FINANCED', 0))
                amount_financed = float(row.get('Financed by Members AMOUNT_FINANCED', 0))
                beginning_outstanding = float(row.get('TO_BOD', 0))
                exposure_taken = float(row.get('ET_DD', 0))
                exposure_liquidated = float(row.get('EL_DD', 0))
                end_outstanding = float(row.get('NO_EOD', 0))

                stock_record = {
                    'date': date.strftime('%Y-%m-%d'),
                    'exchange': 'BSE',
                    'symbol': key,
                    'name': name,
                    'scrip_code': str(row['scrip_code']),
                    'qty_financed': qty_financed,
                    'amount_financed': amount_financed,
                    'beginning_outstanding': beginning_outstanding,
                    'exposure_taken': exposure_taken,
                    'exposure_liquidated': exposure_liquidated,
                    'end_outstanding': end_outstanding,
                    'avg_price': amount_financed / qty_financed if qty_financed > 0 else 0,
                    'net_change': end_outstanding - beginning_outstanding,
                    'activity_ratio': (exposure_taken + exposure_liquidated) / amount_financed if amount_financed > 0 else 0,
                }
                stocks.append(stock_record)
                self.stock_data[key].append(stock_record)
                # Remember every legacy scripname so the post-2025-10
                # resolvers can map new-format rows back to the same bucket.
                self.bse_legacy_scripnames.add(key)
            except (ValueError, KeyError):
                continue
        return stocks

    @staticmethod
    def _word_prefix_match(legacy, words):
        """Can `legacy` be reconstructed by concatenating non-empty prefixes
        of successive words in `words` (with no leftover and no skipped
        word in the middle)? E.g. legacy='RELINFRA', words=['RELIANCE',
        'INFRASTRUCTURE'] succeeds via 'REL'+'INFRA'. Returns the number
        of words consumed (0 if no match)."""
        if not legacy or not words:
            return 0
        def rec(rem, idx):
            if not rem:
                return idx
            if idx >= len(words):
                return 0
            w = words[idx]
            for cut in range(min(len(rem), len(w)), 0, -1):
                if w.startswith(rem[:cut]):
                    n = rec(rem[cut:], idx + 1)
                    if n:
                        return n
            return 0
        return rec(legacy, 0)

    # Confirmed-different-securities exclusions. The word-prefix-match can't
    # algorithmically distinguish these from genuine splits — they share a
    # name prefix but represent different issuers (verified during data audit).
    # Format: (legacy_scripname, joined_new_name_words).
    _BSE_DO_NOT_MERGE = {
        ('RAJNISH',  'RAJNISH RETAIL'),    # Different from BSE legacy RAJNISH.
        ('HERCULES', 'HERCULES HOISTS'),   # HERCULES INVESTMENTS is the real
                                           # continuation; HOISTS is a separate
                                           # listing despite sharing a parent ISIN.
    }

    def _resolve_via_word_prefix(self, name_words):
        """Word-prefix bridge: find a legacy BSE scripname that can be
        reconstructed as concatenated word-prefixes of `name_words`.
        Heuristic rules tuned to capture the known split set without merging
        unrelated securities:
          - legacy must be ≥5 chars (filters HDFC/SIL/MEGH-style coincidences)
          - either match consumes ≥2 word-prefixes (RELINFRA, HINDMOTORS, …)
          - OR legacy exactly equals the first word (HERCULES, KISAN, JOSTS)
        Among candidates, prefer multi-word matches over single-word; tiebreak
        by which legacy bucket has the most existing records (most active)."""
        if not name_words:
            return None
        joined = ' '.join(name_words)
        candidates = []
        for legacy in self.bse_legacy_scripnames:
            if len(legacy) < 5:
                continue
            if (legacy, joined) in self._BSE_DO_NOT_MERGE:
                continue
            n = self._word_prefix_match(legacy, name_words)
            if n >= 2:
                candidates.append((legacy, 2, len(self.stock_data.get(legacy, []))))
            elif legacy == name_words[0]:
                candidates.append((legacy, 1, len(self.stock_data.get(legacy, []))))
        if not candidates:
            return None
        # Multi-word matches win over single-word; then most-active legacy.
        candidates.sort(key=lambda c: (-c[1], -c[2]))
        return candidates[0][0]

    def _extract_bse_new_csv(self, filepath, date):
        """Parse new-format BSE CSV (post-2025-10-03)."""
        import csv as _csv
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Find the securities header row.
        header_idx = -1
        cols = []
        for i, line in enumerate(lines):
            if 'Qty Fin' in line and 'Amt Fin' in line:
                header_idx = i
                cols = [c.strip().lower() for c in line.strip().split(',')]
                break
        if header_idx < 0:
            return []

        # Find the symbol/name/qty/amt column indexes.
        sym_idx = next((i for i, c in enumerate(cols) if c == 'symbol'), -1)
        name_idx = next((i for i, c in enumerate(cols) if c == 'name'), -1)
        isin_idx = next((i for i, c in enumerate(cols) if c == 'isin'), -1)
        qty_idx = next((i for i, c in enumerate(cols) if 'qty fin' in c), -1)
        amt_idx = next((i for i, c in enumerate(cols) if 'amt fin' in c), -1)
        if qty_idx < 0 or amt_idx < 0 or (sym_idx < 0 and name_idx < 0):
            return []

        stocks = []
        reader = _csv.reader(lines[header_idx + 1:])
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            if not first or first.startswith('*') or first.lower() == 'total':
                continue
            if len(row) <= max(qty_idx, amt_idx):
                continue
            try:
                qty_financed = float(row[qty_idx].strip()) if row[qty_idx].strip() else 0
                amount_financed = float(row[amt_idx].strip()) if row[amt_idx].strip() else 0
            except ValueError:
                continue

            # Determine the merge key. Priority order:
            #   1) ISIN → NSE-symbol bridge (best — works for dual-listed stocks
            #      still on NSE, e.g. INFY).
            #   2) 5-col-collapsed-Symbol → legacy bridge — captures stocks
            #      observed in the 30 Sep / 1 Oct / 3 Oct 2025 transitional
            #      CSVs whose whitespace-collapsed Symbol begins with a known
            #      legacy scripname (RELINFRA, SANGHIIND, MANGCHEFER, …).
            #   3) Clean single-token Symbol column value as-is.
            #   4) Word-prefix-match against legacy scripnames (HINDMOTORS=
            #      HIND+MOTORS, MERCURYEV=MERCURY+EV, …).
            #   5) NSE-name bridge — when normalised name matches an NSE
            #      company name (handles polluted Symbol cells like "INFOSYS LTD").
            #   6) Sanitised short-name token (BSE-only listings, genuinely new).
            name = row[name_idx].strip() if name_idx >= 0 and len(row) > name_idx else ''
            isin = row[isin_idx].strip() if isin_idx >= 0 and len(row) > isin_idx else ''
            sym_raw = row[sym_idx].strip() if sym_idx >= 0 and len(row) > sym_idx else ''

            # Feed the 5-col bridge whenever we have BOTH a Symbol and a Name
            # (5-col transitional CSVs; the 4-col Oct+ CSVs don't have Symbol).
            # Pick the LONGEST legacy that prefixes the whitespace-collapsed
            # Symbol — otherwise short scripnames (e.g. CIGNITI vs CIGNITITEC)
            # can shadow the more specific match. ≥5 chars filters 3-4-char
            # legacy tickers (HDFC, SIL, MEGH) that coincidentally prefix
            # unrelated company names ("HDFC AMC" → starts with HDFC).
            if sym_raw and name and not self._looks_like_clean_ticker(sym_raw):
                sym_collapsed = re.sub(r'\s+', '', sym_raw).upper()
                if sym_collapsed:
                    best = ''
                    for legacy in self.bse_legacy_scripnames:
                        if len(legacy) >= 5 and sym_collapsed.startswith(legacy) and len(legacy) > len(best):
                            best = legacy
                    if best:
                        nk = self._bse_key_from_name(name)
                        if nk and nk not in self.bse_name_to_legacy:
                            self.bse_name_to_legacy[nk] = best

            name_key = self._bse_key_from_name(name or sym_raw)
            key = ''
            if isin and isin in self.isin_to_nse_symbol:
                key = self.isin_to_nse_symbol[isin].upper()
            elif name_key and name_key in self.bse_name_to_legacy:
                key = self.bse_name_to_legacy[name_key]
            elif sym_raw and self._looks_like_clean_ticker(sym_raw):
                key = sym_raw.upper()
            else:
                # Word-prefix-match against legacy scripnames.
                name_words = (name or sym_raw).upper()
                name_words = re.sub(r'[^A-Z0-9 &]+', ' ', name_words).split()
                name_words = [w for w in name_words if w not in {
                    'LIMITED','LTD','LIMITE','PVT','PRIVATE','CORPORATION','CORP',
                    'COMPANY','INC','INCORPORATED','INDIA','THE'}]
                wp = self._resolve_via_word_prefix(name_words)
                if wp:
                    key = wp
                else:
                    # Last resort: NSE-name bridge, else the bare name token.
                    key = self.nse_name_to_symbol.get(name_key, name_key)
            if not key:
                continue
            if not name:
                name = sym_raw or key

            stock_record = {
                'date': date.strftime('%Y-%m-%d'),
                'exchange': 'BSE',
                'symbol': key,
                'name': name or key,
                'isin': isin or None,
                'qty_financed': qty_financed,
                'amount_financed': amount_financed,
                # New format doesn't carry per-stock outstanding/exposure breakdowns.
                'beginning_outstanding': None,
                'exposure_taken': None,
                'exposure_liquidated': None,
                'end_outstanding': None,
                'avg_price': amount_financed / qty_financed if qty_financed > 0 else 0,
                'net_change': None,
                'activity_ratio': None,
            }
            stocks.append(stock_record)
            self.stock_data[key].append(stock_record)
        return stocks

    @staticmethod
    def _bse_key_from_name(name: str) -> str:
        """Best-effort merge key from a BSE company name. Strips common suffixes."""
        return _normalize_company_key(name)

    @staticmethod
    def _looks_like_clean_ticker(sym: str) -> bool:
        """Heuristic: a 'real' ticker is a single short token without LTD/LIMITED.
        Polluted BSE 5-col rows put the full company name into the Symbol column
        (e.g. 'INFOSYS LTD', 'ABB LTD') — those should fall through to the name
        bridge so they don't create a phantom bucket per company."""
        s = (sym or '').strip().upper()
        if not s:
            return False
        if ' ' in s:
            return False
        if re.search(r'\b(LIMITED|LTD|LIMITE|PVT|PRIVATE|CORPORATION|CORP|COMPANY|INC|INCORPORATED)\b', s):
            return False
        return True
    
    def calculate_stock_analytics(self):
        """Calculate comprehensive stock analytics with daily time-series data"""
        analytics = {
            'daily_stock_data': {},  # {stock_symbol: [daily_records sorted by date]}
            'latest_snapshot': {
                'nse_stocks': {
                    'top_funded': [],
                    'least_funded': [],
                    'volume_breakers': [],
                    'concentration_analysis': {}
                },
                'bse_stocks': {
                    'top_funded': [],
                    'least_funded': [],
                    'volume_breakers': [],
                    'concentration_analysis': {}
                },
                'combined_stocks': {
                    'top_funded': [],
                    'least_funded': [],
                    'volume_breakers': []
                },
                'sudden_changes': [],
                'cross_exchange_stocks': [],
                'momentum_stocks': []
            },
            'time_series_summary': {
                'date_range': {},
                'total_trading_days': 0,
                'stocks_by_exchange': {}
            }
        }
        
        # Build daily time-series data for each stock
        all_dates = set()
        for symbol, records in self.stock_data.items():
            if records:
                # Sort records by date for time-series analysis
                sorted_records = sorted(records, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
                analytics['daily_stock_data'][symbol] = sorted_records
                
                # Collect all trading dates
                for record in records:
                    all_dates.add(record['date'])
        
        # Calculate time series summary
        if all_dates:
            sorted_dates = sorted(list(all_dates))
            analytics['time_series_summary']['date_range'] = {
                'start_date': sorted_dates[0],
                'end_date': sorted_dates[-1]
            }
            analytics['time_series_summary']['total_trading_days'] = len(sorted_dates)
        
        # Count stocks by exchange over time
        nse_stocks_count = len([s for s, r in self.stock_data.items() if any(record['exchange'] == 'NSE' for record in r)])
        bse_stocks_count = len([s for s, r in self.stock_data.items() if any(record['exchange'] == 'BSE' for record in r)])
        
        analytics['time_series_summary']['stocks_by_exchange'] = {
            'NSE': nse_stocks_count,
            'BSE': bse_stocks_count,
            'total_unique': len(self.stock_data)
        }
        
        # Now calculate latest snapshot for UI display
        latest_data_nse = {}
        latest_data_bse = {}
        latest_data_combined = {}
        
        for symbol, records in self.stock_data.items():
            if records:
                # Separate by exchange
                nse_records = [r for r in records if r['exchange'] == 'NSE']
                bse_records = [r for r in records if r['exchange'] == 'BSE']
                
                if nse_records:
                    latest_nse = max(nse_records, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
                    latest_data_nse[symbol] = latest_nse
                    
                if bse_records:
                    latest_bse = max(bse_records, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
                    latest_data_bse[symbol] = latest_bse
                
                # Combined (use latest record regardless of exchange)
                latest_record = max(records, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
                latest_data_combined[symbol] = latest_record
        
        # NSE Analytics (latest snapshot)
        nse_funded_stocks = [(symbol, data) for symbol, data in latest_data_nse.items() 
                            if data.get('amount_financed', 0) > 0]
        
        analytics['latest_snapshot']['nse_stocks']['top_funded'] = sorted(nse_funded_stocks, 
                                                                        key=lambda x: x[1]['amount_financed'], 
                                                                        reverse=True)[:50]
        analytics['latest_snapshot']['nse_stocks']['least_funded'] = sorted(nse_funded_stocks, 
                                                                          key=lambda x: x[1]['amount_financed'])[:50]
        
        nse_volume_stocks = [(symbol, data) for symbol, data in latest_data_nse.items() 
                           if data.get('qty_financed', 0) > 0]
        analytics['latest_snapshot']['nse_stocks']['volume_breakers'] = sorted(nse_volume_stocks, 
                                                                             key=lambda x: x[1]['qty_financed'], 
                                                                             reverse=True)[:50]
        
        # BSE Analytics (latest snapshot)
        bse_funded_stocks = [(symbol, data) for symbol, data in latest_data_bse.items() 
                            if data.get('amount_financed', 0) > 0]
        
        analytics['latest_snapshot']['bse_stocks']['top_funded'] = sorted(bse_funded_stocks, 
                                                                        key=lambda x: x[1]['amount_financed'], 
                                                                        reverse=True)[:50]
        analytics['latest_snapshot']['bse_stocks']['least_funded'] = sorted(bse_funded_stocks, 
                                                                          key=lambda x: x[1]['amount_financed'])[:50]
        
        bse_volume_stocks = [(symbol, data) for symbol, data in latest_data_bse.items() 
                           if data.get('qty_financed', 0) > 0]
        analytics['latest_snapshot']['bse_stocks']['volume_breakers'] = sorted(bse_volume_stocks, 
                                                                             key=lambda x: x[1]['qty_financed'], 
                                                                             reverse=True)[:50]
        
        # Combined Analytics (latest snapshot)
        combined_funded_stocks = [(symbol, data) for symbol, data in latest_data_combined.items() 
                                 if data.get('amount_financed', 0) > 0]
        
        analytics['latest_snapshot']['combined_stocks']['top_funded'] = sorted(combined_funded_stocks, 
                                                                             key=lambda x: x[1]['amount_financed'], 
                                                                             reverse=True)[:50]
        analytics['latest_snapshot']['combined_stocks']['least_funded'] = sorted(combined_funded_stocks, 
                                                                               key=lambda x: x[1]['amount_financed'])[:50]
        
        combined_volume_stocks = [(symbol, data) for symbol, data in latest_data_combined.items() 
                                 if data.get('qty_financed', 0) > 0]
        analytics['latest_snapshot']['combined_stocks']['volume_breakers'] = sorted(combined_volume_stocks, 
                                                                                  key=lambda x: x[1]['qty_financed'], 
                                                                                  reverse=True)[:50]
        
        # "Biggest movers" in the last 30 days.
        #
        # The previous algorithm only compared each stock's latest record to
        # its ~30-day-old record (±5 days). That misses every intra-window
        # spike: a stock that ran 10 -> 500 on day 15 and crashed back to 10
        # by day 30 would have shown 0% change.
        #
        # New algorithm — for each stock with records inside the trailing
        # 30-day window, find the biggest swing (increase OR decrease)
        # between any two of its records via a single-pass running-min /
        # running-max scan. The reported from_date / to_date are the actual
        # dates of the swing endpoints, not arbitrary 30-day anchors.
        #
        # Filters preserved from before: dust (both endpoints < ₹100 lakh),
        # small moves (|%| < 5), stale stocks (no record in the window).
        # Sort by abs(change_percent), top 50.
        WINDOW_DAYS = 30
        MIN_AMOUNT = 100
        MIN_ABS_PCT = 5

        def _parse(d):
            return datetime.strptime(d, '%Y-%m-%d')

        # Pass 1: anchor = max latest date across all stocks.
        anchor = None
        sorted_by_symbol = {}
        for symbol, records in self.stock_data.items():
            if len(records) < 2:
                continue
            sr = sorted(records, key=lambda r: _parse(r['date']))
            sorted_by_symbol[symbol] = sr
            last_dt = _parse(sr[-1]['date'])
            if anchor is None or last_dt > anchor:
                anchor = last_dt
        cutoff      = (anchor - timedelta(days=WINDOW_DAYS)) if anchor else None
        # Same algorithm applied to the window ending one day earlier — gives
        # us "what the Market Changes row WOULD HAVE looked like yesterday"
        # so the UI can render a side-by-side current-vs-prior comparison.
        prev_anchor = (anchor - timedelta(days=1))         if anchor else None
        prev_cutoff = (prev_anchor - timedelta(days=WINDOW_DAYS)) if prev_anchor else None

        # Best-swing helper — single-pass running-min/max scan.
        def _best_swing(records_window):
            if len(records_window) < 2:
                return None
            first = records_window[0]
            run_min_val = run_max_val = float(first['amount_financed'])
            run_min_rec = run_max_rec = first
            best_pct = 0.0
            best_from = best_to = None
            for r in records_window[1:]:
                cur = float(r['amount_financed'])
                up = (cur - run_min_val) / run_min_val * 100
                if abs(up) > abs(best_pct):
                    best_pct, best_from, best_to = up, run_min_rec, r
                down = (cur - run_max_val) / run_max_val * 100
                if abs(down) > abs(best_pct):
                    best_pct, best_from, best_to = down, run_max_rec, r
                if cur < run_min_val:
                    run_min_val, run_min_rec = cur, r
                if cur > run_max_val:
                    run_max_val, run_max_rec = cur, r
            if best_from is None or best_to is None:
                return None
            if float(best_from['amount_financed']) < MIN_AMOUNT:
                return None
            if abs(best_pct) < MIN_ABS_PCT:
                return None
            return (best_to, best_from, best_pct)

        # Pass 2: for each (stock, exchange) pair, find the biggest swing
        # inside the window.
        #
        # Dual-listed stocks (TCS, HDFCBANK, INFY, etc.) collide on `symbol`
        # because NSE uses the ticker and BSE-legacy uses the same uppercase
        # scrip name. Their NSE and BSE MTF books have totally different
        # magnitudes (TCS NSE ~ ₹1,250 Cr vs TCS BSE ~ ₹35 Cr), so scanning
        # the merged series produces bogus "swings" pairing an NSE day with
        # a BSE day (e.g. ₹25 Cr -> ₹1.3K Cr "+5000%" nonsense). Split by
        # exchange and scan each series independently. A stock that's a real
        # mover on BOTH exchanges legitimately appears twice in the output,
        # with distinct exchange badges.
        sudden_changes = []
        for symbol, sr in sorted_by_symbol.items():
            # Records inside the trailing 30-day window, with amount > 0.
            # Zero-amount rows are "no trading" snapshots rather than legitimate
            # data points and would otherwise produce ∞%-style false positives.
            in_window_all = [
                r for r in sr
                if (cutoff is None or _parse(r['date']) >= cutoff)
                and float(r.get('amount_financed', 0) or 0) > 0
            ]
            if len(in_window_all) < 2:
                continue
            # Same filter on the previous (t-1 ending) window.
            in_prev_all = [
                r for r in sr
                if (prev_cutoff is None or (prev_cutoff <= _parse(r['date']) <= prev_anchor))
                and float(r.get('amount_financed', 0) or 0) > 0
            ]

            by_ex = defaultdict(list)
            for r in in_window_all:
                by_ex[r.get('exchange') or '?'].append(r)
            by_ex_prev = defaultdict(list)
            for r in in_prev_all:
                by_ex_prev[r.get('exchange') or '?'].append(r)

            for ex_name, in_window in by_ex.items():
                cur_swing = _best_swing(in_window)
                if cur_swing is None:
                    continue
                best_to, best_from, best_pct = cur_swing
                # Same algorithm against the t-1 window — gives the prior
                # iteration's biggest swing. May be None if that window has
                # too few records or doesn't pass the size / magnitude filters.
                prev_swing = _best_swing(by_ex_prev.get(ex_name, []))
                sudden_changes.append((symbol, best_to, best_from, best_pct, prev_swing))

        # Sort: most-recent to_date first, tie-break by abs(change_percent).
        # Lexicographic ISO-8601 date comparison gives chronological order.
        # Tuple shape now is (symbol, best_to, best_from, best_pct, prev_swing).
        analytics['latest_snapshot']['sudden_changes'] = sorted(
            sudden_changes,
            key=lambda x: (x[1]['date'], abs(x[3])),
            reverse=True,
        )[:200]
        
        # Unique securities active on each exchange's latest reporting day.
        # The Overview "Securities Total" card uses this to avoid double-counting
        # dual-listed stocks (HDFCBANK, INFY, TCS, …) which appear on both NSE
        # and BSE under different exchange-local symbols.
        #
        # Dedup key: ISIN (International Securities Identification Number) is
        # the same string on both exchanges for a given security, so it's the
        # right key. BSE reports carry ISIN natively; NSE reports don't, so
        # extract_nse_stocks enriches each NSE record via the NSE equity master.
        # If a record lacks an ISIN (rare — fresh listings, ETFs), fall back to
        # a prefixed symbol so it still gets counted exactly once.
        def _key(r):
            isin = (r.get('isin') or '').strip()
            if isin: return isin
            return f"{r.get('exchange','?')}:{r.get('symbol','')}"

        latest_date_nse = max(
            (r['date'] for recs in self.stock_data.values()
             for r in recs if r.get('exchange') == 'NSE'),
            default=None,
        )
        latest_date_bse = max(
            (r['date'] for recs in self.stock_data.values()
             for r in recs if r.get('exchange') == 'BSE'),
            default=None,
        )
        active_nse_keys = {
            _key(r) for recs in self.stock_data.values() for r in recs
            if r.get('exchange') == 'NSE' and r['date'] == latest_date_nse
        }
        active_bse_keys = {
            _key(r) for recs in self.stock_data.values() for r in recs
            if r.get('exchange') == 'BSE' and r['date'] == latest_date_bse
        }
        dual_active_keys = active_nse_keys & active_bse_keys
        analytics['latest_snapshot']['active_securities'] = {
            'nse_count':   len(active_nse_keys),
            'bse_count':   len(active_bse_keys),
            'dual_listed': len(dual_active_keys),
            'unique':      len(active_nse_keys | active_bse_keys),
            'as_of_nse':   latest_date_nse,
            'as_of_bse':   latest_date_bse,
            'dedup_key':   'ISIN (with exchange:symbol fallback)',
        }

        # Cross-exchange analysis (full-history set intersection — separate
        # from the latest-day "dual_active" above. The dashboard uses this
        # list for the Cross-Exchange tab's deep-dive.)
        nse_symbols = set(latest_data_nse.keys())
        bse_symbols = set(latest_data_bse.keys())
        cross_exchange_symbols = nse_symbols.intersection(bse_symbols)
        
        # Create cross-exchange stock details
        cross_exchange_details = []
        for symbol in cross_exchange_symbols:
            nse_data = latest_data_nse.get(symbol)
            bse_data = latest_data_bse.get(symbol)
            
            if nse_data and bse_data:
                cross_exchange_details.append({
                    'symbol': symbol,
                    'name': nse_data.get('name', bse_data.get('name', symbol)),
                    'nse_data': nse_data,
                    'bse_data': bse_data,
                    'total_funding': nse_data.get('amount_financed', 0) + bse_data.get('amount_financed', 0),
                    'funding_difference': abs(nse_data.get('amount_financed', 0) - bse_data.get('amount_financed', 0))
                })
        
        analytics['latest_snapshot']['cross_exchange_stocks'] = sorted(cross_exchange_details, 
                                                                     key=lambda x: x['total_funding'], 
                                                                     reverse=True)[:50]
        
        # Market concentration analysis for each exchange
        # NSE Concentration
        nse_total_funding = sum(data['amount_financed'] for _, data in latest_data_nse.items())
        nse_top_10_funding = sum(data['amount_financed'] for _, data in analytics['latest_snapshot']['nse_stocks']['top_funded'][:10])
        nse_top_50_funding = sum(data['amount_financed'] for _, data in analytics['latest_snapshot']['nse_stocks']['top_funded'][:50])
        
        analytics['latest_snapshot']['nse_stocks']['concentration_analysis'] = {
            'total_funding': nse_total_funding,
            'total_stocks': len(latest_data_nse),
            'top_10_share': (nse_top_10_funding / nse_total_funding * 100) if nse_total_funding > 0 else 0,
            'top_50_share': (nse_top_50_funding / nse_total_funding * 100) if nse_total_funding > 0 else 0,
        }
        
        # BSE Concentration
        bse_total_funding = sum(data['amount_financed'] for _, data in latest_data_bse.items())
        bse_top_10_funding = sum(data['amount_financed'] for _, data in analytics['latest_snapshot']['bse_stocks']['top_funded'][:10])
        bse_top_50_funding = sum(data['amount_financed'] for _, data in analytics['latest_snapshot']['bse_stocks']['top_funded'][:50])
        
        analytics['latest_snapshot']['bse_stocks']['concentration_analysis'] = {
            'total_funding': bse_total_funding,
            'total_stocks': len(latest_data_bse),
            'top_10_share': (bse_top_10_funding / bse_total_funding * 100) if bse_total_funding > 0 else 0,
            'top_50_share': (bse_top_50_funding / bse_total_funding * 100) if bse_total_funding > 0 else 0,
        }
        
        return analytics
    
    def export_analytics(self, analytics, output_path):
        """Export analytics to JSON file for dashboard consumption"""
        
        def format_stock_list(stock_list):
            return [
                {
                    'symbol': symbol,
                    'name': data.get('name', symbol),
                    'exchange': data['exchange'],
                    'amount_financed': data['amount_financed'],
                    'qty_financed': data.get('qty_financed', 0),
                    'avg_price': data.get('avg_price', 0),
                    'date': data['date']
                }
                for symbol, data in stock_list
            ]
        
        # Convert analytics to serializable format
        export_data = {
            # Daily time-series data for all stocks (this is the main addition!)
            'daily_stock_data': analytics['daily_stock_data'],
            'time_series_summary': analytics['time_series_summary'],
            
            # Latest snapshot for current dashboard UI (backward compatibility)
            'nse_stocks': {
                'top_funded': format_stock_list(analytics['latest_snapshot']['nse_stocks']['top_funded']),
                'least_funded': format_stock_list(analytics['latest_snapshot']['nse_stocks']['least_funded']),
                'volume_breakers': format_stock_list(analytics['latest_snapshot']['nse_stocks']['volume_breakers']),
                'concentration_analysis': analytics['latest_snapshot']['nse_stocks']['concentration_analysis']
            },
            'bse_stocks': {
                'top_funded': format_stock_list(analytics['latest_snapshot']['bse_stocks']['top_funded']),
                'least_funded': format_stock_list(analytics['latest_snapshot']['bse_stocks']['least_funded']),
                'volume_breakers': format_stock_list(analytics['latest_snapshot']['bse_stocks']['volume_breakers']),
                'concentration_analysis': analytics['latest_snapshot']['bse_stocks']['concentration_analysis']
            },
            'combined_stocks': {
                'top_funded': format_stock_list(analytics['latest_snapshot']['combined_stocks']['top_funded']),
                'least_funded': format_stock_list(analytics['latest_snapshot']['combined_stocks']['least_funded']),
                'volume_breakers': format_stock_list(analytics['latest_snapshot']['combined_stocks']['volume_breakers'])
            },
            'sudden_changes': [
                {
                    'symbol':          symbol,
                    'name':            latest.get('name', symbol),
                    'exchange':        latest['exchange'],
                    'amount_financed': latest['amount_financed'],
                    'previous_amount': prev['amount_financed'],
                    'change_percent':  change_pct,
                    'from_date':       prev['date'],
                    'to_date':         latest['date'],
                    # Same swing computation against the window ending one day
                    # earlier (anchor − 1 → anchor − 31). Lets the UI render a
                    # side-by-side "today vs yesterday's snapshot of the same
                    # 30-day window" comparison. None if the prior window had
                    # too few records / didn't pass size + magnitude filters.
                    **({
                        'prev_iter_amount':           prev_swing[0]['amount_financed'],
                        'prev_iter_previous_amount':  prev_swing[1]['amount_financed'],
                        'prev_iter_change_percent':   prev_swing[2],
                        'prev_iter_from_date':        prev_swing[1]['date'],
                        'prev_iter_to_date':          prev_swing[0]['date'],
                    } if prev_swing else {}),
                }
                for symbol, latest, prev, change_pct, prev_swing in analytics['latest_snapshot']['sudden_changes']
            ],
            'cross_exchange_stocks': analytics['latest_snapshot']['cross_exchange_stocks'],
            'active_securities': analytics['latest_snapshot']['active_securities'],
            'extraction_date': datetime.now().isoformat(),
            'total_stock_records': sum(len(records) for records in self.stock_data.values())
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Stock analytics exported to {output_path}")
        
    def run_extraction(self, sample_size=None):
        """Run the complete stock extraction process"""
        logger.info("Starting stock-level MTF data extraction...")
        
        total_files_processed = 0
        total_stocks_extracted = 0
        
        # Process NSE files
        nse_dir = "mtf_reports/NSE"
        if os.path.exists(nse_dir):
            nse_files = sorted([f for f in os.listdir(nse_dir) if f.endswith('.zip')])
            if sample_size:
                nse_files = nse_files[-sample_size:]  # Take recent files for sample
            logger.info(f"Processing {len(nse_files)} NSE files (filter: dates >= {MIN_DATE.date()})...")

            for i, filename in enumerate(nse_files):
                if i % 200 == 0:
                    logger.info(f"  NSE {i}/{len(nse_files)}  ({total_stocks_extracted:,} records so far)")
                filepath = os.path.join(nse_dir, filename)
                date_str = filename.replace('NSE_MTF_', '').replace('.zip', '')
                try:
                    date = datetime.strptime(date_str, '%d%m%Y')
                    if date < MIN_DATE:
                        continue
                    stocks = self.extract_nse_stocks(filepath, date)
                    total_stocks_extracted += len(stocks)
                    total_files_processed += 1
                except Exception as e:
                    logger.warning(f"Failed to process {filename}: {e}")
                    continue

        # Process BSE files (both legacy .xls and new .csv formats)
        bse_dir = "mtf_reports/BSE"
        if os.path.exists(bse_dir):
            # Sort by trade DATE (not filename) so legacy .xls files (all
            # pre-2025-10) are processed before .csv files (post-2025-09-30).
            # Order matters: the BSE bridges built in __init__ depend on legacy
            # scripnames being known before any 4-col CSV row is resolved.
            def _bse_parse_date(fn):
                try:
                    return datetime.strptime(fn.replace('BSE_MTF_','').rsplit('.',1)[0], '%d%m%Y')
                except ValueError:
                    return datetime.max
            bse_files = sorted(
                [f for f in os.listdir(bse_dir)
                 if f.startswith('BSE_MTF_') and f.endswith(('.xls', '.csv'))],
                key=_bse_parse_date,
            )
            if sample_size:
                bse_files = bse_files[-sample_size:]
            xls_n = sum(1 for f in bse_files if f.endswith('.xls'))
            csv_n = sum(1 for f in bse_files if f.endswith('.csv'))
            logger.info(f"Processing {len(bse_files)} BSE files (legacy .xls: {xls_n}, new .csv: {csv_n}, filter: dates >= {MIN_DATE.date()})...")

            for i, filename in enumerate(bse_files):
                if i % 200 == 0:
                    logger.info(f"  BSE {i}/{len(bse_files)}  ({total_stocks_extracted:,} records so far)")
                filepath = os.path.join(bse_dir, filename)
                date_str = filename.replace('BSE_MTF_', '').rsplit('.', 1)[0]
                try:
                    date = datetime.strptime(date_str, '%d%m%Y')
                    if date < MIN_DATE:
                        continue
                    stocks = self.extract_bse_stocks(filepath, date)
                    total_stocks_extracted += len(stocks)
                    total_files_processed += 1
                except Exception as e:
                    logger.warning(f"Failed to process {filename}: {e}")
                    continue
        
        logger.info(f"Extraction complete!")
        logger.info(f"Files processed: {total_files_processed}")
        logger.info(f"Stock records extracted: {total_stocks_extracted}")
        logger.info(f"Unique stocks found: {len(self.stock_data)}")
        
        # Calculate analytics
        logger.info("Calculating stock analytics...")
        analytics = self.calculate_stock_analytics()
        
        # Export results
        output_file = "stock_analytics.json"
        self.export_analytics(analytics, output_file)
        
        # Print summary
        print("\n" + "="*80)
        print("STOCK-LEVEL MTF ANALYTICS SUMMARY")
        print("="*80)
        print(f"Total unique stocks analyzed: {len(self.stock_data):,}")
        print(f"Total stock records processed: {total_stocks_extracted:,}")
        print(f"NSE stocks: {analytics['latest_snapshot']['nse_stocks']['concentration_analysis']['total_stocks']:,}")
        print(f"BSE stocks: {analytics['latest_snapshot']['bse_stocks']['concentration_analysis']['total_stocks']:,}")
        print(f"Cross-exchange stocks: {len(analytics['latest_snapshot']['cross_exchange_stocks']):,}")
        print(f"NSE Market concentration (Top 10): {analytics['latest_snapshot']['nse_stocks']['concentration_analysis']['top_10_share']:.1f}%")
        print(f"BSE Market concentration (Top 10): {analytics['latest_snapshot']['bse_stocks']['concentration_analysis']['top_10_share']:.1f}%")
        
        # Additional time-series info
        ts = analytics['time_series_summary']
        if 'date_range' in ts and ts['date_range']:
            print(f"Date range: {ts['date_range']['start_date']} to {ts['date_range']['end_date']}")
            print(f"Total trading days: {ts['total_trading_days']:,}")
        print(f"Daily time-series data available for {len(analytics['daily_stock_data']):,} stocks")
        print(f"Output file: {output_file}")
        
        return analytics

def main():
    """Main execution function"""
    extractor = StockMTFExtractor()
    
    # Process all files for complete time period data
    analytics = extractor.run_extraction()  # Process all files
    
    print("\nStock analytics extraction completed successfully!")
    print("Use 'stock_analytics.json' file to power the stock analytics dashboard.")

if __name__ == "__main__":
    main()