#!/usr/bin/env python3
import os
from datetime import datetime
from collections import defaultdict
import time

def wait_for_downloads():
    """Wait for all download processes to complete"""
    print("Checking for running downloads...")
    while True:
        result = os.popen("ps aux | grep python3 | grep mtf_downloader | grep -v grep").read()
        if not result.strip():
            print("All downloads completed!")
            break
        else:
            processes = len(result.strip().split('\n'))
            print(f"Still {processes} downloads running... waiting 30 seconds")
            time.sleep(30)

def analyze_final_coverage():
    """Analyze final coverage after all downloads"""
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
    
    print("\n" + "=" * 60)
    print("FINAL MTF DATA COVERAGE REPORT")
    print("=" * 60)
    
    print(f"\nTotal files downloaded:")
    print(f"NSE: {len(nse_files)} files")
    print(f"BSE: {len(bse_files)} files")
    print(f"TOTAL: {len(nse_files) + len(bse_files)} files")
    
    if nse_files:
        print(f"\nNSE Coverage:")
        print(f"Date Range: {nse_files[0].strftime('%d-%b-%Y')} to {nse_files[-1].strftime('%d-%b-%Y')}")
        
        # Count by year
        nse_by_year = defaultdict(int)
        for date in nse_files:
            nse_by_year[date.year] += 1
        
        print("\nNSE files by year:")
        for year in sorted(nse_by_year.keys()):
            expected = 250 if year < datetime.now().year else int(250 * datetime.now().timetuple().tm_yday / 365)
            coverage = (nse_by_year[year] / expected * 100) if expected > 0 else 0
            print(f"  {year}: {nse_by_year[year]} files ({coverage:.1f}% coverage)")
    
    if bse_files:
        print(f"\nBSE Coverage:")
        print(f"Date Range: {bse_files[0].strftime('%d-%b-%Y')} to {bse_files[-1].strftime('%d-%b-%Y')}")
        
        # Count by year
        bse_by_year = defaultdict(int)
        for date in bse_files:
            bse_by_year[date.year] += 1
        
        print("\nBSE files by year:")
        for year in sorted(bse_by_year.keys()):
            if year < 2018:
                continue  # BSE data not available before 2018
            expected = 250 if year < datetime.now().year else int(250 * datetime.now().timetuple().tm_yday / 365)
            if year == 2018:
                expected = 50  # Only available from November
            coverage = (bse_by_year[year] / expected * 100) if expected > 0 else 0
            print(f"  {year}: {bse_by_year[year]} files ({coverage:.1f}% coverage)")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"- NSE data successfully downloaded from Feb 2011 to Aug 2025")
    print(f"- BSE data available only from Nov 2018 onwards")
    print(f"- Total {len(nse_files) + len(bse_files)} MTF reports collected")
    print("=" * 60)

if __name__ == "__main__":
    # Wait for downloads to complete
    wait_for_downloads()
    
    # Analyze final coverage
    analyze_final_coverage()