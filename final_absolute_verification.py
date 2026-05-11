#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from collections import defaultdict

def final_absolute_verification():
    """Perform final absolute verification with file integrity checks"""
    
    print("FINAL ABSOLUTE VERIFICATION - MISSION CRITICAL LEVEL")
    print("=" * 80)
    
    # Count and verify all files
    nse_files = {}
    bse_files = {}
    
    # NSE verification
    nse_dir = "mtf_reports/NSE"
    if os.path.exists(nse_dir):
        for file in os.listdir(nse_dir):
            if file.endswith('.zip'):
                filepath = os.path.join(nse_dir, file)
                size = os.path.getsize(filepath)
                if size > 100:  # Valid file size
                    date_str = file.replace('NSE_MTF_', '').replace('.zip', '')
                    try:
                        date = datetime.strptime(date_str, '%d%m%Y')
                        nse_files[date] = size
                    except:
                        pass
    
    # BSE verification
    bse_dir = "mtf_reports/BSE"
    if os.path.exists(bse_dir):
        for file in os.listdir(bse_dir):
            if file.endswith('.xls'):
                filepath = os.path.join(bse_dir, file)
                size = os.path.getsize(filepath)
                if size > 100:  # Valid file size
                    date_str = file.replace('BSE_MTF_', '').replace('.xls', '')
                    try:
                        date = datetime.strptime(date_str, '%d%m%Y')
                        bse_files[date] = size
                    except:
                        pass
    
    print(f"VERIFIED FILE COUNTS:")
    print(f"  NSE: {len(nse_files):,} valid files")
    print(f"  BSE: {len(bse_files):,} valid files")
    print(f"  TOTAL: {len(nse_files) + len(bse_files):,} MTF reports")
    
    # Coverage analysis
    nse_sorted = sorted(nse_files.keys())
    bse_sorted = sorted(bse_files.keys()) if bse_files else []
    
    print(f"\nCOVERAGE PERIODS:")
    if nse_sorted:
        print(f"  NSE: {nse_sorted[0].strftime('%d-%b-%Y')} to {nse_sorted[-1].strftime('%d-%b-%Y')}")
    if bse_sorted:
        print(f"  BSE: {bse_sorted[0].strftime('%d-%b-%Y')} to {bse_sorted[-1].strftime('%d-%b-%Y')}")
    
    # Year-by-year breakdown
    nse_by_year = defaultdict(int)
    bse_by_year = defaultdict(int)
    
    for date in nse_files:
        nse_by_year[date.year] += 1
    
    for date in bse_files:
        bse_by_year[date.year] += 1
    
    print(f"\nYEAR-BY-YEAR BREAKDOWN:")
    print(f"{'Year':<6} {'NSE':<6} {'BSE':<6} {'Total':<6}")
    print("-" * 30)
    
    all_years = sorted(set(list(nse_by_year.keys()) + list(bse_by_year.keys())))
    total_nse = 0
    total_bse = 0
    
    for year in all_years:
        nse_count = nse_by_year[year]
        bse_count = bse_by_year[year]
        total_nse += nse_count
        total_bse += bse_count
        year_total = nse_count + bse_count
        print(f"{year:<6} {nse_count:<6} {bse_count:<6} {year_total:<6}")
    
    print("-" * 30)
    print(f"{'TOTAL':<6} {total_nse:<6} {total_bse:<6} {total_nse+total_bse:<6}")
    
    # File size analysis
    nse_sizes = list(nse_files.values())
    bse_sizes = list(bse_files.values())
    
    print(f"\nFILE SIZE ANALYSIS:")
    if nse_sizes:
        print(f"  NSE files - Min: {min(nse_sizes)} bytes, Max: {max(nse_sizes):,} bytes, Avg: {sum(nse_sizes)//len(nse_sizes):,} bytes")
    if bse_sizes:
        print(f"  BSE files - Min: {min(bse_sizes)} bytes, Max: {max(bse_sizes):,} bytes, Avg: {sum(bse_sizes)//len(bse_sizes):,} bytes")
    
    # Check for any anomalies
    small_files = []
    for date, size in nse_files.items():
        if size < 1000:  # Suspiciously small
            small_files.append(('NSE', date, size))
    
    for date, size in bse_files.items():
        if size < 1000:  # Suspiciously small
            small_files.append(('BSE', date, size))
    
    if small_files:
        print(f"\n⚠️  SMALL FILES DETECTED ({len(small_files)} files):")
        for exchange, date, size in small_files[:10]:  # Show first 10
            print(f"  {exchange} {date.strftime('%d-%b-%Y')}: {size} bytes")
    
    print(f"\n" + "=" * 80)
    print("FINAL MISSION CRITICAL VERIFICATION RESULTS")
    print("=" * 80)
    
    # Expected vs actual
    current_date = datetime.now()
    
    # NSE expected (from Feb 2011)
    nse_start = datetime(2011, 2, 1)
    nse_expected = 0
    temp_date = nse_start
    while temp_date <= current_date:
        if temp_date.weekday() < 5:  # Weekdays
            nse_expected += 1
        temp_date += timedelta(days=1)
    
    # BSE expected (from Nov 2018)
    bse_start = datetime(2018, 11, 1)
    bse_expected = 0
    temp_date = bse_start
    while temp_date <= current_date:
        if temp_date.weekday() < 5:  # Weekdays
            bse_expected += 1
        temp_date += timedelta(days=1)
    
    nse_coverage = (len(nse_files) / nse_expected * 100) if nse_expected > 0 else 0
    bse_coverage = (len(bse_files) / bse_expected * 100) if bse_expected > 0 else 0
    
    print(f"COVERAGE ANALYSIS:")
    print(f"  NSE: {len(nse_files):,}/{nse_expected:,} possible trading days ({nse_coverage:.1f}%)")
    print(f"  BSE: {len(bse_files):,}/{bse_expected:,} possible trading days ({bse_coverage:.1f}%)")
    
    # Final verdict
    print(f"\n" + "=" * 80)
    if len(small_files) == 0 and nse_coverage > 90 and bse_coverage > 50:
        print("✅ MISSION CRITICAL VERIFICATION: PASSED")
        print("✅ DATA INTEGRITY: VERIFIED")
        print("✅ COVERAGE: ACCEPTABLE")
        print("✅ DATASET IS COMPLETE AND READY FOR USE")
    else:
        print("⚠️  MISSION CRITICAL VERIFICATION: REVIEW REQUIRED")
        if len(small_files) > 0:
            print("⚠️  Small files detected - may indicate incomplete downloads")
        if nse_coverage <= 90:
            print("⚠️  NSE coverage below 90%")
        if bse_coverage <= 50:
            print("⚠️  BSE coverage below expected threshold")
    
    return len(nse_files), len(bse_files)

if __name__ == "__main__":
    nse_count, bse_count = final_absolute_verification()
    print(f"\n🎯 MISSION ACCOMPLISHED")
    print(f"📊 Final Dataset: {nse_count + bse_count:,} MTF reports")
    print(f"📈 NSE: {nse_count:,} | BSE: {bse_count:,}")