#!/usr/bin/env python3
import requests
import time
from datetime import datetime, timedelta
import os

class NSEDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.nse_base_url = "https://www.nseindia.com"
        self.output_dir = "mtf_reports/NSE"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set comprehensive headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
    
    def initialize_session(self):
        """Initialize session with proper cookie chain"""
        print("Step 1: Visiting NSE homepage...")
        try:
            # First visit the homepage
            response = self.session.get(self.nse_base_url, timeout=30)
            print(f"Homepage status: {response.status_code}")
            print(f"Cookies after homepage: {self.session.cookies.get_dict()}")
            time.sleep(2)
            
            # Visit the reports main page
            print("\nStep 2: Visiting all-reports page...")
            reports_url = f"{self.nse_base_url}/all-reports"
            headers = {
                'Referer': self.nse_base_url,
                'Sec-Fetch-Site': 'same-origin'
            }
            response = self.session.get(reports_url, headers=headers, timeout=30)
            print(f"Reports page status: {response.status_code}")
            print(f"Cookies after reports page: {self.session.cookies.get_dict()}")
            time.sleep(2)
            
            # Visit the API endpoint to establish API session
            print("\nStep 3: Testing API endpoint...")
            test_date = "01-Aug-2025"
            api_url = f"{self.nse_base_url}/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={test_date}&type=equities&mode=single"
            
            api_headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.nseindia.com/all-reports',
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            response = self.session.get(api_url, headers=api_headers, timeout=30)
            print(f"API test status: {response.status_code}")
            print(f"Final cookies: {self.session.cookies.get_dict()}")
            
            if response.status_code == 200:
                print("Session initialized successfully!")
                return True
            else:
                print(f"API test failed. Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"Error initializing session: {e}")
            return False
    
    def download_report(self, date):
        """Download NSE MTF report for a specific date"""
        date_str = date.strftime("%d-%b-%Y")
        filename = f"NSE_MTF_{date.strftime('%d%m%Y')}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        if os.path.exists(filepath) or os.path.exists(filepath.replace('.csv', '.zip')):
            print(f"NSE report for {date_str} already exists, skipping...")
            return True
        
        url = f"{self.nse_base_url}/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={date_str}&type=equities&mode=single"
        
        try:
            print(f"\nDownloading NSE report for {date_str}...")
            
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.nseindia.com/all-reports',
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                
                if 'application/json' in content_type:
                    try:
                        data = response.json()
                        if data and len(data) > 0 and 'link' in data[0]:
                            download_url = data[0]['link']
                            print(f"Found download link: {download_url}")
                            
                            # Download the actual file
                            file_response = self.session.get(download_url, timeout=30)
                            if file_response.status_code == 200:
                                # Check if it's a zip file
                                if file_response.content[:2] == b'PK':
                                    filepath = filepath.replace('.csv', '.zip')
                                
                                with open(filepath, 'wb') as f:
                                    f.write(file_response.content)
                                print(f"Successfully downloaded NSE report for {date_str}")
                                return True
                        else:
                            print(f"No download link in response for {date_str}")
                            return False
                    except ValueError as e:
                        print(f"JSON parsing error: {e}")
                        return False
                else:
                    # Direct download
                    if len(response.content) > 0:
                        if response.content[:2] == b'PK':
                            filepath = filepath.replace('.csv', '.zip')
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        print(f"Successfully downloaded NSE report for {date_str}")
                        return True
            else:
                print(f"Failed with status {response.status_code}")
                if response.status_code == 401:
                    print("Session expired, reinitializing...")
                    if self.initialize_session():
                        return self.download_report(date)  # Retry once
                return False
                
        except Exception as e:
            print(f"Error downloading NSE report for {date_str}: {e}")
            return False

def main():
    downloader = NSEDownloader()
    
    # Initialize session with proper cookie chain
    if not downloader.initialize_session():
        print("Failed to initialize session. Trying anyway...")
    
    # Download from August 6, 2025 to today
    start_date = datetime(2025, 8, 6)
    end_date = datetime.now()
    current_date = start_date
    
    successful = 0
    failed = 0
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() in [5, 6]:
            current_date += timedelta(days=1)
            continue
        
        if downloader.download_report(current_date):
            successful += 1
        else:
            failed += 1
        
        time.sleep(3)  # Be respectful with delays
        current_date += timedelta(days=1)
    
    print(f"\n=== Summary ===")
    print(f"Successful downloads: {successful}")
    print(f"Failed downloads: {failed}")

if __name__ == "__main__":
    main()