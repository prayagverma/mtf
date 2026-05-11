#!/usr/bin/env python3
import requests
import time
import os
from datetime import datetime

class SpecificDownloader:
    def __init__(self):
        self.bse_session = requests.Session()
        self.bse_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.bseindia.com'
        })
    
    def download_bse_file(self, date):
        """Download specific BSE file"""
        date_str = date.strftime("%d%m%Y")
        url = f"https://www.bseindia.com/markets/downloads/MarginTrading_{date_str}.xls"
        filename = f"BSE_MTF_{date_str}.xls"
        filepath = os.path.join("mtf_reports/BSE", filename)
        
        if os.path.exists(filepath):
            print(f"File already exists: {filename}")
            return True
        
        try:
            print(f"Downloading BSE {date.strftime('%d-%b-%Y')}...")
            response = self.bse_session.get(url, timeout=30)
            
            if response.status_code == 200 and len(response.content) > 0:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Successfully downloaded: {filename}")
                return True
            else:
                print(f"❌ Failed to download: {filename} (Status: {response.status_code})")
                return False
        except Exception as e:
            print(f"❌ Error downloading {filename}: {e}")
            return False

def main():
    # Missing files identified
    missing_dates = [
        datetime(2025, 7, 7),   # 07-Jul-2025
        datetime(2022, 6, 15),  # 15-Jun-2022
        datetime(2020, 1, 8),   # 08-Jan-2020
        datetime(2020, 1, 29),  # 29-Jan-2020
        datetime(2020, 2, 5),   # 05-Feb-2020
        datetime(2020, 8, 26),  # 26-Aug-2020
        datetime(2020, 9, 16),  # 16-Sep-2020
        datetime(2020, 12, 16), # 16-Dec-2020
        datetime(2020, 12, 30), # 30-Dec-2020
    ]
    
    downloader = SpecificDownloader()
    
    print("DOWNLOADING SPECIFIC MISSING BSE FILES")
    print("=" * 50)
    
    success_count = 0
    for date in missing_dates:
        if downloader.download_bse_file(date):
            success_count += 1
        time.sleep(1)  # Rate limiting
    
    print(f"\n{'='*50}")
    print(f"Downloaded {success_count} out of {len(missing_dates)} files")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()