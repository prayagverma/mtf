#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from collections import defaultdict
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

def get_trading_days_count(year):
    """Calculate expected trading days for a year (excluding weekends)"""
    if year == datetime.now().year:
        end_date = datetime.now()
    else:
        end_date = datetime(year, 12, 31)
    
    start_date = datetime(year, 1, 1)
    
    trading_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday to Friday
            trading_days += 1
        current += timedelta(days=1)
    
    return trading_days

def analyze_yearly_breakdown():
    """Analyze year-by-year breakdown"""
    nse_dates = get_downloaded_dates("NSE")
    bse_dates = get_downloaded_dates("BSE")
    
    # Group by year
    nse_by_year = defaultdict(list)
    bse_by_year = defaultdict(list)
    
    for date in nse_dates:
        nse_by_year[date.year].append(date)
    
    for date in bse_dates:
        bse_by_year[date.year].append(date)
    
    print("DETAILED YEAR-BY-YEAR MTF DATA BREAKDOWN")
    print("=" * 80)
    
    # Get all years from 2011 to current year
    current_year = datetime.now().year
    all_years = range(2011, current_year + 1)
    
    total_nse = 0
    total_bse = 0
    
    for year in all_years:
        nse_count = len(nse_by_year[year])
        bse_count = len(bse_by_year[year])
        
        total_nse += nse_count
        total_bse += bse_count
        
        if year == 2011:
            # NSE started in February 2011
            expected_days = get_trading_days_count(year) - get_trading_days_count_before_feb(year)
        else:
            expected_days = get_trading_days_count(year)
        
        print(f"\n{year}:")
        print(f"{'='*50}")
        
        # NSE Analysis
        if nse_count > 0:
            nse_coverage = (nse_count / expected_days * 100) if expected_days > 0 else 0
            print(f"NSE: {nse_count:3d} files ({nse_coverage:5.1f}% coverage)")
            
            if nse_by_year[year]:
                nse_sorted = sorted(nse_by_year[year])
                print(f"     Range: {nse_sorted[0].strftime('%d-%b-%Y')} to {nse_sorted[-1].strftime('%d-%b-%Y')}")
        else:
            print(f"NSE:   0 files (  0.0% coverage) - No data available")
        
        # BSE Analysis
        if year >= 2018:  # BSE started in Nov 2018
            if year == 2018:
                bse_expected = 43  # Nov-Dec 2018 trading days approx
            else:
                bse_expected = expected_days
                
            if bse_count > 0:
                bse_coverage = (bse_count / bse_expected * 100) if bse_expected > 0 else 0
                print(f"BSE: {bse_count:3d} files ({bse_coverage:5.1f}% coverage)")
                
                if bse_by_year[year]:
                    bse_sorted = sorted(bse_by_year[year])
                    print(f"     Range: {bse_sorted[0].strftime('%d-%b-%Y')} to {bse_sorted[-1].strftime('%d-%b-%Y')}")
            else:
                print(f"BSE:   0 files (  0.0% coverage) - No data available")
        else:
            print(f"BSE:   - files (     - coverage) - Service not available before Nov 2018")
        
        # Monthly breakdown for recent/important years
        if year in [2015, 2021, 2024, current_year]:
            print(f"\n     Monthly breakdown for {year}:")
            for month in range(1, 13):
                if year == current_year and month > datetime.now().month:
                    break
                    
                month_nse = len([d for d in nse_by_year[year] if d.month == month])
                month_bse = len([d for d in bse_by_year[year] if d.month == month]) if year >= 2018 else 0
                
                month_name = calendar.month_abbr[month]
                if month_nse > 0 or month_bse > 0:
                    print(f"     {month_name}: NSE={month_nse:2d}, BSE={month_bse:2d}")
        
        print(f"Expected trading days: ~{expected_days}")
    
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    print(f"Total NSE files: {total_nse:,}")
    print(f"Total BSE files: {total_bse:,}")
    print(f"Grand Total: {total_nse + total_bse:,} MTF reports")
    print(f"\nCoverage Period:")
    print(f"NSE: February 2011 - August 2025 (14.5 years)")
    print(f"BSE: November 2018 - August 2025 (6.8 years)")
    
    # Calculate average files per year
    nse_years = current_year - 2011 + 1
    bse_years = current_year - 2018 + 1
    
    print(f"\nAverage files per year:")
    print(f"NSE: {total_nse / nse_years:.0f} files/year")
    print(f"BSE: {total_bse / bse_years:.0f} files/year")

def get_trading_days_count_before_feb(year):
    """Get trading days count before February"""
    count = 0
    current = datetime(year, 1, 1)
    end = datetime(year, 1, 31)
    
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    
    return count

if __name__ == "__main__":
    analyze_yearly_breakdown()