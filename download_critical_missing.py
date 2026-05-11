#!/usr/bin/env python3
import requests
import time
import os
from datetime import datetime

def download_critical_missing():
    """Download the critical missing files identified"""
    
    critical_missing = [
        datetime(2018, 11, 1),   # 01-Nov-2018
        datetime(2019, 6, 21),   # 21-Jun-2019
        datetime(2019, 10, 29),  # 29-Oct-2019
        datetime(2020, 3, 19),   # 19-Mar-2020
        datetime(2020, 12, 14),  # 14-Dec-2020
        datetime(2022, 11, 2),   # 02-Nov-2022
        datetime(2023, 4, 12),   # 12-Apr-2023
        datetime(2023, 8, 23),   # 23-Aug-2023
        datetime(2023, 11, 1),   # 01-Nov-2023
        datetime(2024, 3, 1),    # 01-Mar-2024
        datetime(2024, 10, 7),   # 07-Oct-2024
        datetime(2024, 12, 24),  # 24-Dec-2024
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Referer': 'https://www.bseindia.com'
    })
    
    print("DOWNLOADING CRITICAL MISSING BSE FILES")
    print("=" * 50)
    
    success_count = 0
    
    for date in critical_missing:
        date_str = date.strftime("%d%m%Y")
        url = f"https://www.bseindia.com/markets/downloads/MarginTrading_{date_str}.xls"
        filename = f"BSE_MTF_{date_str}.xls"
        filepath = f"mtf_reports/BSE/{filename}"
        
        print(f"Downloading {date.strftime('%d-%b-%Y')}...")
        
        try:
            response = session.get(url, timeout=30)
            
            if response.status_code == 200 and len(response.content) > 100:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"✅ SUCCESS: {filename}")
                success_count += 1
            else:
                print(f"❌ FAILED: {filename} (Status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ ERROR: {filename} - {e}")
        
        time.sleep(1)  # Rate limiting
    
    print(f"\n{'='*50}")
    print(f"CRITICAL DOWNLOAD COMPLETE")
    print(f"Successfully downloaded: {success_count}/{len(critical_missing)} files")
    print(f"{'='*50}")
    
    return success_count

if __name__ == "__main__":
    download_critical_missing()