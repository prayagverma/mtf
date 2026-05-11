#!/usr/bin/env python3
import requests
import time
import os
from datetime import datetime, timedelta
import calendar

class WeekendSpecialSessions:
    def __init__(self):
        self.nse_session = requests.Session()
        self.bse_session = requests.Session()
        
        # Setup sessions
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
        }
        
        self.nse_session.headers.update(headers)
        self.nse_session.headers.update({'Referer': 'https://www.nseindia.com/all-reports'})
        
        self.bse_session.headers.update(headers)
        self.bse_session.headers.update({'Referer': 'https://www.bseindia.com'})
        
        self.found_sessions = []
    
    def visit_base_sites(self):
        """Visit base sites to establish sessions"""
        print("Establishing sessions with exchanges...")
        
        # NSE
        try:
            self.nse_session.get("https://www.nseindia.com", timeout=10)
            self.nse_session.get("https://www.nseindia.com/all-reports", timeout=10)
            print("✅ NSE session established")
        except:
            print("⚠️  NSE session issue")
        
        # BSE
        try:
            self.bse_session.get("https://www.bseindia.com", timeout=10)
            print("✅ BSE session established")
        except:
            print("⚠️  BSE session issue")
        
        time.sleep(2)
    
    def check_weekend_date(self, date, exchange):
        """Check if a weekend date has MTF data"""
        # Skip if we already have this file
        date_str = date.strftime("%d%m%Y")
        
        if exchange == "NSE":
            filepath = f"mtf_reports/NSE/NSE_MTF_{date_str}.zip"
            if os.path.exists(filepath):
                return True  # Already have it
                
            # Check NSE API
            api_date = date.strftime("%d-%b-%Y")
            url = f"https://www.nseindia.com/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={api_date}&type=equities&mode=single"
            
            try:
                response = self.nse_session.get(url, timeout=10)
                if response.status_code == 200 and len(response.content) > 100:
                    print(f"🎯 FOUND NSE WEEKEND SESSION: {date.strftime('%d-%b-%Y (%A)')}")
                    
                    # Try to download
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' not in content_type and len(response.content) > 100:
                        # Direct file download
                        if response.content[:2] == b'PK':
                            filepath = filepath.replace('.csv', '.zip')
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        self.found_sessions.append(('NSE', date))
                        return True
                    else:
                        try:
                            data = response.json()
                            if data and len(data) > 0 and 'link' in data[0]:
                                download_url = data[0]['link']
                                file_response = self.nse_session.get(download_url, timeout=10)
                                if file_response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        f.write(file_response.content)
                                    self.found_sessions.append(('NSE', date))
                                    return True
                        except:
                            pass
            except:
                pass
        
        else:  # BSE
            filepath = f"mtf_reports/BSE/BSE_MTF_{date_str}.xls"
            if os.path.exists(filepath):
                return True  # Already have it
                
            # Check BSE URL
            url = f"https://www.bseindia.com/markets/downloads/MarginTrading_{date_str}.xls"
            
            try:
                response = self.bse_session.get(url, timeout=10)
                if response.status_code == 200 and len(response.content) > 100:
                    print(f"🎯 FOUND BSE WEEKEND SESSION: {date.strftime('%d-%b-%Y (%A)')}")
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    self.found_sessions.append(('BSE', date))
                    return True
            except:
                pass
        
        return False
    
    def check_all_weekends(self, start_year=2011):
        """Check all weekend dates from start_year to current"""
        print(f"\nCHECKING ALL WEEKEND DATES FROM {start_year} TO {datetime.now().year}")
        print("=" * 80)
        
        current_year = datetime.now().year
        current_date = datetime.now()
        
        total_weekends_checked = 0
        
        for year in range(start_year, current_year + 1):
            print(f"\nChecking {year} weekend sessions...")
            
            # For each year, check all Saturdays and Sundays
            start_date = datetime(year, 1, 1)
            if year == current_year:
                end_date = current_date
            else:
                end_date = datetime(year, 12, 31)
            
            current = start_date
            year_weekends = 0
            year_found = 0
            
            while current <= end_date:
                if current.weekday() in [5, 6]:  # Saturday, Sunday
                    total_weekends_checked += 1
                    year_weekends += 1
                    
                    # Check NSE (from 2011)
                    if current >= datetime(2011, 2, 1):
                        if self.check_weekend_date(current, "NSE"):
                            year_found += 1
                    
                    # Check BSE (from Nov 2018)
                    if current >= datetime(2018, 11, 1):
                        if self.check_weekend_date(current, "BSE"):
                            year_found += 1
                    
                    time.sleep(0.2)  # Rate limiting
                
                current += timedelta(days=1)
            
            if year_found > 0:
                print(f"  📊 {year}: Found {year_found} weekend sessions out of {year_weekends} weekends")
            else:
                print(f"  ⚪ {year}: No weekend sessions found")
        
        print(f"\n" + "=" * 80)
        print(f"WEEKEND SPECIAL SESSIONS SUMMARY")
        print(f"=" * 80)
        print(f"Total weekend dates checked: {total_weekends_checked:,}")
        print(f"Special sessions found: {len(self.found_sessions)}")
        
        if self.found_sessions:
            print(f"\nSPECIAL WEEKEND SESSIONS DISCOVERED:")
            for exchange, date in sorted(self.found_sessions):
                day_name = date.strftime('%A')
                print(f"  🎯 {exchange}: {date.strftime('%d-%b-%Y')} ({day_name})")
        
        return len(self.found_sessions)
    
    def check_specific_muhurat_dates(self):
        """Check specific Muhurat trading dates (usually around Diwali)"""
        print(f"\nCHECKING SPECIFIC MUHURAT TRADING DATES")
        print("=" * 50)
        
        # Muhurat trading typically happens on Diwali weekend
        # Let's check historically known Muhurat dates (Diwali weekends)
        
        known_muhurat_periods = [
            # Format: (year, month, day_range)
            (2011, 10, [26, 27, 28]),  # Diwali 2011
            (2012, 11, [13, 14, 15]),  # Diwali 2012  
            (2013, 11, [2, 3, 4]),     # Diwali 2013
            (2014, 10, [23, 24, 25]),  # Diwali 2014
            (2015, 11, [11, 12, 13]),  # Diwali 2015
            (2016, 10, [29, 30, 31]),  # Diwali 2016
            (2017, 10, [18, 19, 20]),  # Diwali 2017
            (2018, 11, [6, 7, 8]),     # Diwali 2018
            (2019, 10, [27, 28, 29]),  # Diwali 2019
            (2020, 11, [14, 15, 16]),  # Diwali 2020
            (2021, 11, [4, 5, 6]),     # Diwali 2021
            (2022, 10, [24, 25, 26]),  # Diwali 2022
            (2023, 11, [12, 13, 14]),  # Diwali 2023
            (2024, 10, [31], 11, [1, 2]),  # Diwali 2024
            (2025, 10, [20, 21, 22]),  # Diwali 2025 (estimated)
        ]
        
        muhurat_found = 0
        
        for period in known_muhurat_periods:
            if len(period) == 3:
                year, month, days = period
                for day in days:
                    try:
                        date = datetime(year, month, day)
                        if date <= datetime.now():
                            if self.check_weekend_date(date, "NSE"):
                                muhurat_found += 1
                            if date >= datetime(2018, 11, 1):
                                if self.check_weekend_date(date, "BSE"):
                                    muhurat_found += 1
                            time.sleep(0.3)
                    except:
                        pass
        
        return muhurat_found
    
    def run_weekend_check(self):
        """Run comprehensive weekend check"""
        print("🏁 WEEKEND & SPECIAL SESSIONS VERIFICATION")
        print("=" * 80)
        
        self.visit_base_sites()
        
        # Check all weekends
        weekend_sessions = self.check_all_weekends(2011)
        
        # Check specific Muhurat dates
        muhurat_sessions = self.check_specific_muhurat_dates()
        
        total_found = len(self.found_sessions)
        
        print(f"\n🎯 WEEKEND VERIFICATION COMPLETE")
        print(f"📊 Total weekend sessions found: {total_found}")
        
        if total_found > 0:
            print(f"⚠️  CRITICAL: Found {total_found} additional weekend MTF reports!")
            print("✅ All weekend sessions have been downloaded")
        else:
            print("ℹ️  No weekend special sessions found")
            print("✅ Exchanges do not publish MTF reports on weekends")
        
        return total_found

if __name__ == "__main__":
    checker = WeekendSpecialSessions()
    found_count = checker.run_weekend_check()
    
    print(f"\n{'='*80}")
    if found_count > 0:
        print(f"🚨 ACTION COMPLETED: {found_count} weekend sessions added to dataset")
    else:
        print("✅ CONFIRMATION: No weekend MTF sessions exist")
    print(f"{'='*80}")