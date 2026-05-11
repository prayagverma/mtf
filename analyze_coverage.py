#!/usr/bin/env python3
import os
from datetime import datetime
from collections import defaultdict

def analyze_mtf_coverage():
    nse_files = []
    bse_files = []
    
    # Collect NSE files
    nse_dir = "mtf_reports/NSE"
    if os.path.exists(nse_dir):
        for file in os.listdir(nse_dir):
            if file.endswith('.zip'):
                try:
                    date_str = file.replace('NSE_MTF_', '').replace('.zip', '')
                    date = datetime.strptime(date_str, '%d%m%Y')
                    nse_files.append(date)
                except:
                    pass
    
    # Collect BSE files
    bse_dir = "mtf_reports/BSE"
    if os.path.exists(bse_dir):
        for file in os.listdir(bse_dir):
            if file.endswith('.xls'):
                try:
                    date_str = file.replace('BSE_MTF_', '').replace('.xls', '')
                    date = datetime.strptime(date_str, '%d%m%Y')
                    bse_files.append(date)
                except:
                    pass
    
    # Sort files
    nse_files.sort()
    bse_files.sort()
    
    # Analyze coverage
    print("MTF DATA COVERAGE ANALYSIS")
    print("=" * 50)
    
    print(f"\nTotal files downloaded:")
    print(f"NSE: {len(nse_files)} files")
    print(f"BSE: {len(bse_files)} files")
    
    if nse_files:
        print(f"\nNSE Coverage:")
        print(f"Earliest: {nse_files[0].strftime('%d-%b-%Y')}")
        print(f"Latest: {nse_files[-1].strftime('%d-%b-%Y')}")
        
        # Count by year
        nse_by_year = defaultdict(int)
        for date in nse_files:
            nse_by_year[date.year] += 1
        
        print("\nNSE files by year:")
        for year in sorted(nse_by_year.keys()):
            print(f"  {year}: {nse_by_year[year]} files")
    
    if bse_files:
        print(f"\nBSE Coverage:")
        print(f"Earliest: {bse_files[0].strftime('%d-%b-%Y')}")
        print(f"Latest: {bse_files[-1].strftime('%d-%b-%Y')}")
        
        # Count by year
        bse_by_year = defaultdict(int)
        for date in bse_files:
            bse_by_year[date.year] += 1
        
        print("\nBSE files by year:")
        for year in sorted(bse_by_year.keys()):
            print(f"  {year}: {bse_by_year[year]} files")
    
    # Check for gaps
    print("\n" + "=" * 50)
    print("COVERAGE GAPS ANALYSIS")
    
    # Expected trading days per year (approximate)
    expected_days = 250
    
    print("\nYears with potentially missing data:")
    all_years = set()
    if nse_files:
        all_years.update(range(nse_files[0].year, nse_files[-1].year + 1))
    if bse_files:
        all_years.update(range(bse_files[0].year, bse_files[-1].year + 1))
    
    for year in sorted(all_years):
        nse_count = nse_by_year.get(year, 0)
        bse_count = bse_by_year.get(year, 0)
        
        if year == datetime.now().year:
            # Adjust for current year
            days_passed = (datetime.now() - datetime(year, 1, 1)).days
            expected_days = int(250 * days_passed / 365)
        
        if nse_count < expected_days * 0.8 or bse_count < expected_days * 0.8:
            print(f"  {year}: NSE={nse_count}, BSE={bse_count} (expected ~{expected_days})")

if __name__ == "__main__":
    analyze_mtf_coverage()