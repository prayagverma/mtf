#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
import calendar

def get_trading_days(start_date, end_date):
    """Generate expected trading days (weekdays) between two dates"""
    trading_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday to Friday
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days

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

def find_missing_dates(exchange, year, month=None):
    """Find missing dates for a specific year/month"""
    if month:
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day)
    else:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
    
    # Adjust end date for current year
    if end_date > datetime.now():
        end_date = datetime.now()
    
    expected_days = get_trading_days(start_date, end_date)
    downloaded_dates = get_downloaded_dates(exchange)
    
    missing_dates = []
    for date in expected_days:
        if date not in downloaded_dates:
            missing_dates.append(date)
    
    return missing_dates

def main():
    print("MISSING MTF REPORTS ANALYSIS")
    print("=" * 60)
    
    # Check NSE 2015 specifically
    print("\nNSE 2015 Missing Dates:")
    nse_2015_missing = find_missing_dates("NSE", 2015)
    print(f"Total missing: {len(nse_2015_missing)} days")
    if len(nse_2015_missing) <= 20:
        for date in sorted(nse_2015_missing)[:20]:
            print(f"  - {date.strftime('%d-%b-%Y')}")
    else:
        # Group by month
        by_month = {}
        for date in nse_2015_missing:
            month_key = date.strftime('%B %Y')
            if month_key not in by_month:
                by_month[month_key] = 0
            by_month[month_key] += 1
        
        for month, count in sorted(by_month.items(), key=lambda x: datetime.strptime(x[0], '%B %Y')):
            print(f"  - {month}: {count} missing days")
    
    # Check NSE 2024
    print("\nNSE 2024 Missing Dates:")
    nse_2024_missing = find_missing_dates("NSE", 2024)
    print(f"Total missing: {len(nse_2024_missing)} days")
    
    # Check BSE gaps
    print("\nBSE Coverage Gaps:")
    for year in [2019, 2020, 2021, 2022]:
        missing = find_missing_dates("BSE", year)
        if missing:
            print(f"\n{year}: {len(missing)} missing days")
            if len(missing) <= 10:
                for date in sorted(missing)[:10]:
                    print(f"  - {date.strftime('%d-%b-%Y')}")
    
    # Generate download commands
    print("\n" + "=" * 60)
    print("SUGGESTED DOWNLOAD COMMANDS:")
    
    # For NSE 2015
    if len(nse_2015_missing) > 100:
        print("\n# Download entire NSE 2015:")
        print("python3 mtf_downloader.py --year 2015 --exchange NSE")
    
    # For NSE 2024
    if len(nse_2024_missing) > 50:
        print("\n# Download NSE 2024 from April onwards:")
        print("python3 mtf_downloader.py --year 2024 --exchange NSE")
    
    # Export missing dates to file
    with open("missing_dates.txt", "w") as f:
        f.write("Missing MTF Report Dates\n")
        f.write("=" * 40 + "\n\n")
        
        f.write("NSE 2015 Missing Dates:\n")
        for date in sorted(nse_2015_missing):
            f.write(f"{date.strftime('%d-%b-%Y')}\n")
        
        f.write("\n\nNSE 2024 Missing Dates:\n")
        for date in sorted(nse_2024_missing):
            f.write(f"{date.strftime('%d-%b-%Y')}\n")
    
    print("\nMissing dates exported to: missing_dates.txt")

if __name__ == "__main__":
    main()