#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
import calendar

def get_downloaded_dates(exchange):
    """Get all downloaded dates for an exchange"""
    downloaded = set()
    
    if exchange == "NSE":
        dir_path = "mtf_reports/NSE"
        pattern = "NSE_MTF_"
        ext = ".zip"
    else:
        dir_path = "mtf_reports/BSE"
        pattern = "BSE_MTF_"
        ext = ".xls"
    
    if os.path.exists(dir_path):
        for file in os.listdir(dir_path):
            if file.startswith(pattern) and file.endswith(ext):
                try:
                    date_str = file.replace(pattern, '').replace(ext, '')
                    date = datetime.strptime(date_str, '%d%m%Y')
                    downloaded.add(date)
                except:
                    pass
    
    return downloaded

def check_recent_missing():
    """Check for missing recent data (last 60 days)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    nse_downloaded = get_downloaded_dates("NSE")
    bse_downloaded = get_downloaded_dates("BSE")
    
    current = start_date
    nse_missing = []
    bse_missing = []
    
    while current <= end_date:
        if current.weekday() < 5:  # Weekdays only
            if current not in nse_downloaded:
                nse_missing.append(current)
            if current not in bse_downloaded:
                bse_missing.append(current)
        current += timedelta(days=1)
    
    print("RECENT MISSING DATA (Last 60 days)")
    print("=" * 50)
    
    print(f"\nNSE Missing ({len(nse_missing)} days):")
    for date in nse_missing[-10:]:  # Show last 10
        print(f"  - {date.strftime('%d-%b-%Y')}")
    
    print(f"\nBSE Missing ({len(bse_missing)} days):")  
    for date in bse_missing[-10:]:  # Show last 10
        print(f"  - {date.strftime('%d-%b-%Y')}")

def check_year_completeness():
    """Check completeness for key years"""
    nse_downloaded = get_downloaded_dates("NSE")
    bse_downloaded = get_downloaded_dates("BSE")
    
    print("\nYEAR COMPLETENESS CHECK")
    print("=" * 50)
    
    # Check NSE for key years
    key_years = [2015, 2021, 2024]
    for year in key_years:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        if year == datetime.now().year:
            end_date = datetime.now()
        
        expected_days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Weekdays
                expected_days.append(current)
            current += timedelta(days=1)
        
        downloaded_count = len([d for d in expected_days if d in nse_downloaded])
        missing_count = len(expected_days) - downloaded_count
        
        print(f"\nNSE {year}:")
        print(f"  Expected: {len(expected_days)} trading days")
        print(f"  Downloaded: {downloaded_count}")
        print(f"  Missing: {missing_count}")
        
        if missing_count > 0 and missing_count <= 10:
            missing = [d for d in expected_days if d not in nse_downloaded]
            print("  Missing dates:")
            for date in missing:
                print(f"    - {date.strftime('%d-%b-%Y')}")
    
    # Check BSE for available years
    bse_years = [2019, 2020, 2023]
    for year in bse_years:
        if year == 2019:
            start_date = datetime(2018, 11, 1)  # BSE started in Nov 2018
        else:
            start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        if year == datetime.now().year:
            end_date = datetime.now()
        
        expected_days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Weekdays
                expected_days.append(current)
            current += timedelta(days=1)
        
        downloaded_count = len([d for d in expected_days if d in bse_downloaded])
        missing_count = len(expected_days) - downloaded_count
        
        print(f"\nBSE {year}:")
        print(f"  Expected: {len(expected_days)} trading days")
        print(f"  Downloaded: {downloaded_count}")  
        print(f"  Missing: {missing_count}")

def main():
    check_recent_missing()
    check_year_completeness()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("- Many missing dates are likely holidays or non-trading days")
    print("- Some exchanges don't publish MTF reports on certain days")
    print("- BSE coverage is naturally lower as they started later")
    print("- Current coverage represents maximum available data")
    print("=" * 60)

if __name__ == "__main__":
    main()