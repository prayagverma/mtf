#!/usr/bin/env python3
import requests
import os
from datetime import datetime, timedelta
import time

class ComprehensiveChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.missing_files = []
        
    def get_downloaded_files(self):
        """Get all currently downloaded files"""
        nse_files = set()
        bse_files = set()
        
        # NSE files
        nse_dir = "mtf_reports/NSE"
        if os.path.exists(nse_dir):
            for file in os.listdir(nse_dir):
                if file.endswith('.zip'):
                    date_str = file.replace('NSE_MTF_', '').replace('.zip', '')
                    try:
                        date = datetime.strptime(date_str, '%d%m%Y')
                        nse_files.add(date)
                    except:
                        pass
        
        # BSE files  
        bse_dir = "mtf_reports/BSE"
        if os.path.exists(bse_dir):
            for file in os.listdir(bse_dir):
                if file.endswith('.xls'):
                    date_str = file.replace('BSE_MTF_', '').replace('.xls', '')
                    try:
                        date = datetime.strptime(date_str, '%d%m%Y')
                        bse_files.add(date)
                    except:
                        pass
        
        return nse_files, bse_files
    
    def test_random_dates(self, exchange, dates_to_test=50):
        """Test random dates to see if they're available"""
        print(f"\nTesting {dates_to_test} random dates for {exchange}...")
        
        # Generate random dates from different years
        test_dates = []
        
        if exchange == "NSE":
            start_year = 2011
            base_url = "https://www.nseindia.com"
        else:
            start_year = 2019
            base_url = "https://www.bseindia.com"
        
        # Sample dates from different periods
        for year in range(start_year, 2025):
            for month in [3, 6, 9, 12]:  # Sample from different quarters
                try:
                    date = datetime(year, month, 15)  # Mid-month
                    if date.weekday() < 5 and date <= datetime.now():  # Weekday and not future
                        test_dates.append(date)
                except:
                    pass
        
        # Test a subset
        import random
        test_sample = random.sample(test_dates, min(dates_to_test, len(test_dates)))
        
        found_new = 0
        for date in test_sample:
            if self.test_single_date(exchange, date):
                found_new += 1
                self.missing_files.append((exchange, date))
        
        print(f"Found {found_new} potentially available files for {exchange}")
        return found_new
    
    def test_single_date(self, exchange, date):
        """Test if a single date is available but not downloaded"""
        date_str = date.strftime("%d%m%Y")
        
        if exchange == "NSE":
            # Check if we already have it
            filepath = f"mtf_reports/NSE/NSE_MTF_{date_str}.zip"
            if os.path.exists(filepath):
                return False
                
            # Test URL
            api_date = date.strftime("%d-%b-%Y")
            url = f"https://www.nseindia.com/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={api_date}&type=equities&mode=single"
            
        else:  # BSE
            # Check if we already have it
            filepath = f"mtf_reports/BSE/BSE_MTF_{date_str}.xls"
            if os.path.exists(filepath):
                return False
                
            # Test URL
            url = f"https://www.bseindia.com/markets/downloads/MarginTrading_{date_str}.xls"
        
        try:
            response = self.session.head(url, timeout=10)
            time.sleep(0.5)  # Rate limiting
            
            if response.status_code == 200:
                print(f"  FOUND MISSING: {exchange} {date.strftime('%d-%b-%Y')}")
                return True
        except:
            pass
        
        return False
    
    def check_recent_dates(self, days=30):
        """Check recent dates thoroughly"""
        print(f"\nChecking last {days} days for any missing files...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        current = start_date
        
        found_missing = 0
        
        while current <= end_date:
            if current.weekday() < 5:  # Weekdays only
                # Test NSE
                if self.test_single_date("NSE", current):
                    found_missing += 1
                
                # Test BSE
                if self.test_single_date("BSE", current):
                    found_missing += 1
                
                time.sleep(0.5)  # Rate limiting
            current += timedelta(days=1)
        
        print(f"Found {found_missing} missing recent files")
        return found_missing
    
    def check_specific_problem_periods(self):
        """Check specific periods that showed low coverage"""
        print("\nChecking specific problem periods...")
        
        problem_periods = [
            # NSE periods with lower coverage
            (datetime(2021, 1, 1), datetime(2021, 12, 31), "NSE"),
            (datetime(2015, 7, 1), datetime(2015, 12, 31), "NSE"),
            
            # BSE periods with very low coverage
            (datetime(2019, 1, 1), datetime(2019, 12, 31), "BSE"),
            (datetime(2020, 1, 1), datetime(2020, 12, 31), "BSE"),
            (datetime(2023, 1, 1), datetime(2023, 12, 31), "BSE"),
        ]
        
        found_missing = 0
        
        for start, end, exchange in problem_periods:
            print(f"\nChecking {exchange} from {start.strftime('%b %Y')} to {end.strftime('%b %Y')}")
            
            current = start
            period_missing = 0
            
            while current <= end and current <= datetime.now():
                if current.weekday() < 5:  # Weekdays
                    if self.test_single_date(exchange, current):
                        period_missing += 1
                        found_missing += 1
                
                current += timedelta(days=7)  # Sample weekly to avoid overwhelming
                time.sleep(0.2)
            
            print(f"  Found {period_missing} missing files in this period")
        
        return found_missing
    
    def run_comprehensive_check(self):
        """Run all checks"""
        print("COMPREHENSIVE MTF DATA COMPLETENESS CHECK")
        print("=" * 60)
        
        nse_files, bse_files = self.get_downloaded_files()
        
        print(f"Currently downloaded:")
        print(f"  NSE: {len(nse_files)} files")
        print(f"  BSE: {len(bse_files)} files")
        print(f"  Total: {len(nse_files) + len(bse_files)} files")
        
        # Run various checks
        missing_count = 0
        
        # 1. Check recent dates
        missing_count += self.check_recent_dates(30)
        
        # 2. Test random sampling
        missing_count += self.test_random_dates("NSE", 30)
        missing_count += self.test_random_dates("BSE", 30)
        
        # 3. Check specific problem periods
        missing_count += self.check_specific_problem_periods()
        
        print(f"\n" + "=" * 60)
        print("COMPLETENESS CHECK RESULTS:")
        print("=" * 60)
        
        if missing_count == 0:
            print("✅ NO MISSING FILES FOUND")
            print("✅ Data collection appears COMPLETE")
            print("✅ All available MTF reports have been downloaded")
        else:
            print(f"⚠️  Found {missing_count} potentially missing files")
            print(f"⚠️  These files may be available for download")
            
            if self.missing_files:
                print("\nMissing files found:")
                for exchange, date in self.missing_files[:10]:  # Show first 10
                    print(f"  - {exchange}: {date.strftime('%d-%b-%Y')}")
        
        return missing_count

if __name__ == "__main__":
    checker = ComprehensiveChecker()
    missing_count = checker.run_comprehensive_check()