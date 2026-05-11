#!/usr/bin/env python3
import subprocess
import time
import os
from datetime import datetime, timedelta
import calendar
import argparse
import tempfile

class MTFDownloaderCurl:
    def __init__(self, output_dir="mtf_reports", delay=2):
        self.output_dir = output_dir
        self.delay = delay
        self.bse_base_url = "https://www.bseindia.com"
        self.nse_base_url = "https://www.nseindia.com"
        
        # Create output directories
        self.bse_dir = os.path.join(output_dir, "BSE")
        self.nse_dir = os.path.join(output_dir, "NSE")
        os.makedirs(self.bse_dir, exist_ok=True)
        os.makedirs(self.nse_dir, exist_ok=True)
        
        # Create cookie files
        self.bse_cookie_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_bse_cookies.txt')
        self.nse_cookie_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_nse_cookies.txt')
        self.bse_cookie_file.close()
        self.nse_cookie_file.close()
        
        print(f"BSE cookie file: {self.bse_cookie_file.name}")
        print(f"NSE cookie file: {self.nse_cookie_file.name}")
    
    def __del__(self):
        # Clean up cookie files
        try:
            if hasattr(self, 'bse_cookie_file'):
                os.unlink(self.bse_cookie_file.name)
            if hasattr(self, 'nse_cookie_file'):
                os.unlink(self.nse_cookie_file.name)
        except:
            pass
    
    def visit_base_site(self, exchange):
        """Visit the base website to get cookies using curl"""
        print(f"Visiting {exchange} base site to get cookies...")
        
        if exchange == "BSE":
            cookie_file = self.bse_cookie_file.name
            base_url = self.bse_base_url
        else:
            cookie_file = self.nse_cookie_file.name
            base_url = self.nse_base_url
        
        # Visit base site and save cookies
        cmd = [
            'curl', '-s', '-c', cookie_file, '-b', cookie_file,
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '-H', 'Accept-Language: en-US,en;q=0.9',
            base_url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Successfully visited {exchange} base site")
                
                # For NSE, also visit the reports page
                if exchange == "NSE":
                    time.sleep(self.delay)
                    reports_url = f"{self.nse_base_url}/all-reports"
                    cmd[cmd.index(base_url)] = reports_url
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Successfully visited {exchange} reports page")
                
                time.sleep(self.delay)
                return True
            else:
                print(f"Failed to visit {exchange} base site")
                return False
        except Exception as e:
            print(f"Error visiting {exchange} base site: {e}")
            return False
    
    def download_bse_report(self, date):
        """Download BSE MTF report for a specific date using curl"""
        date_str = date.strftime("%d%m%Y")
        url = f"{self.bse_base_url}/markets/downloads/MarginTrading_{date_str}.xls"
        filename = f"BSE_MTF_{date_str}.xls"
        filepath = os.path.join(self.bse_dir, filename)
        
        if os.path.exists(filepath):
            print(f"BSE report for {date_str} already exists, skipping...")
            return True
        
        print(f"Downloading BSE report for {date_str}...")
        
        cmd = [
            'curl', '-s', '-c', self.bse_cookie_file.name, '-b', self.bse_cookie_file.name,
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-H', 'Accept: */*',
            '-H', f'Referer: {self.bse_base_url}',
            '-o', filepath,
            '-w', '%{http_code}',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            http_code = result.stdout.strip()
            
            if result.returncode == 0 and http_code == '200' and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"Successfully downloaded BSE report for {date_str}")
                return True
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                print(f"BSE report not available for {date_str} (HTTP: {http_code})")
                return False
        except Exception as e:
            print(f"Error downloading BSE report for {date_str}: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return False
    
    def download_nse_report(self, date):
        """Download NSE MTF report for a specific date using curl"""
        date_str = date.strftime("%d-%b-%Y")
        url = f"{self.nse_base_url}/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={date_str}&type=equities&mode=single"
        
        filename = f"NSE_MTF_{date.strftime('%d%m%Y')}"
        filepath = os.path.join(self.nse_dir, filename)
        
        # Check for both .csv and .zip extensions
        if os.path.exists(filepath + '.csv') or os.path.exists(filepath + '.zip'):
            print(f"NSE report for {date_str} already exists, skipping...")
            return True
        
        print(f"Downloading NSE report for {date_str}...")
        
        # Download directly - NSE now returns the file directly
        temp_filepath = filepath + '.tmp'
        cmd = [
            'curl', '-s', '-c', self.nse_cookie_file.name, '-b', self.nse_cookie_file.name,
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-H', 'Accept: application/json, text/plain, */*',
            '-H', f'Referer: {self.nse_base_url}/all-reports',
            '-H', 'X-Requested-With: XMLHttpRequest',
            '-o', temp_filepath,
            '-w', '%{http_code}',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            http_code = result.stdout.strip()
            
            if result.returncode == 0 and http_code == '200' and os.path.exists(temp_filepath) and os.path.getsize(temp_filepath) > 0:
                # Check if it's a ZIP file (starts with PK)
                with open(temp_filepath, 'rb') as f:
                    header = f.read(2)
                    
                if header == b'PK':
                    final_filepath = filepath + '.zip'
                else:
                    # Check if it's JSON
                    try:
                        with open(temp_filepath, 'r') as f:
                            import json
                            data = json.load(f)
                            
                        # If it's JSON with a link, download the actual file
                        if data and len(data) > 0 and 'link' in data[0]:
                            download_url = data[0]['link']
                            os.remove(temp_filepath)
                            
                            # Download the actual file
                            cmd = [
                                'curl', '-s', '-c', self.nse_cookie_file.name, '-b', self.nse_cookie_file.name,
                                '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                '-H', 'Accept: */*',
                                '-H', f'Referer: {self.nse_base_url}/all-reports',
                                '-o', temp_filepath,
                                '-w', '%{http_code}',
                                download_url
                            ]
                            
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            http_code = result.stdout.strip()
                            
                            if result.returncode == 0 and http_code == '200' and os.path.exists(temp_filepath) and os.path.getsize(temp_filepath) > 0:
                                with open(temp_filepath, 'rb') as f:
                                    header = f.read(2)
                                final_filepath = filepath + '.zip' if header == b'PK' else filepath + '.csv'
                            else:
                                if os.path.exists(temp_filepath):
                                    os.remove(temp_filepath)
                                print(f"Failed to download NSE file for {date_str} (HTTP: {http_code})")
                                return False
                        else:
                            os.remove(temp_filepath)
                            print(f"NSE report not available for {date_str}")
                            return False
                    except (json.JSONDecodeError, KeyError):
                        # It's likely a CSV file
                        final_filepath = filepath + '.csv'
                
                # Move to final location
                os.rename(temp_filepath, final_filepath)
                print(f"Successfully downloaded NSE report for {date_str}")
                return True
            else:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                print(f"NSE report not available for {date_str} (HTTP: {http_code})")
                return False
        except Exception as e:
            print(f"Error downloading NSE report for {date_str}: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return False
    
    def download_all_reports(self, start_date, end_date, exchange="both"):
        """Download all reports between start_date and end_date"""
        current_date = start_date
        
        # Visit base sites first
        if exchange in ["both", "BSE"]:
            if not self.visit_base_site("BSE"):
                print("Warning: Could not visit BSE base site")
        
        if exchange in ["both", "NSE"]:
            if not self.visit_base_site("NSE"):
                print("Warning: Could not visit NSE base site")
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() in [5, 6]:  # Saturday, Sunday
                current_date += timedelta(days=1)
                continue
            
            # Download BSE report
            if exchange in ["both", "BSE"]:
                self.download_bse_report(current_date)
                time.sleep(self.delay)
            
            # Download NSE report
            if exchange in ["both", "NSE"]:
                self.download_nse_report(current_date)
                time.sleep(self.delay)
            
            current_date += timedelta(days=1)
    
    def download_last_n_days(self, days=30, exchange="both"):
        """Download reports for the last n days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        self.download_all_reports(start_date, end_date, exchange)
    
    def download_month(self, year, month, exchange="both"):
        """Download all reports for a specific month"""
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day)
        self.download_all_reports(start_date, end_date, exchange)
    
    def download_year(self, year, exchange="both"):
        """Download all reports for a specific year"""
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        if year == datetime.now().year:
            end_date = datetime.now()
        self.download_all_reports(start_date, end_date, exchange)

def main():
    parser = argparse.ArgumentParser(description="Download MTF reports from BSE and NSE using curl")
    parser.add_argument("--start-year", type=int, default=2011, help="Start year (default: 2011)")
    parser.add_argument("--end-year", type=int, default=datetime.now().year, help="End year (default: current year)")
    parser.add_argument("--exchange", choices=["BSE", "NSE", "both"], default="both", help="Exchange to download from")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests in seconds (default: 2)")
    parser.add_argument("--output-dir", default="mtf_reports", help="Output directory (default: mtf_reports)")
    parser.add_argument("--month", type=int, help="Download specific month (1-12)")
    parser.add_argument("--year", type=int, help="Download specific year")
    parser.add_argument("--last-days", type=int, help="Download last n days")
    
    args = parser.parse_args()
    
    downloader = MTFDownloaderCurl(output_dir=args.output_dir, delay=args.delay)
    
    if args.last_days:
        print(f"Downloading reports for last {args.last_days} days...")
        downloader.download_last_n_days(args.last_days, args.exchange)
    elif args.month and args.year:
        print(f"Downloading reports for {args.month}/{args.year}...")
        downloader.download_month(args.year, args.month, args.exchange)
    elif args.year and not args.month:
        print(f"Downloading reports for year {args.year}...")
        downloader.download_year(args.year, args.exchange)
    else:
        print(f"Downloading reports from {args.start_year} to {args.end_year}...")
        for year in range(args.start_year, args.end_year + 1):
            print(f"\nProcessing year {year}...")
            downloader.download_year(year, args.exchange)
            time.sleep(downloader.delay * 2)  # Extra delay between years

if __name__ == "__main__":
    main()