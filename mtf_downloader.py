#!/usr/bin/env python3
import requests
import time
import os
from datetime import datetime, timedelta
import calendar
import argparse
import http.cookiejar

class MTFDownloader:
    def __init__(self, output_dir="mtf_reports", delay=2):
        self.output_dir = output_dir
        self.delay = delay
        self.bse_base_url = "https://www.bseindia.com"
        self.nse_base_url = "https://www.nseindia.com"
        
        # Create separate sessions for each exchange
        self.bse_session = requests.Session()
        self.nse_session = requests.Session()
        
        # Create output directories
        self.bse_dir = os.path.join(output_dir, "BSE")
        self.nse_dir = os.path.join(output_dir, "NSE")
        os.makedirs(self.bse_dir, exist_ok=True)
        os.makedirs(self.nse_dir, exist_ok=True)
        
        # Set common headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.bse_session.headers.update(self.headers)
        self.nse_session.headers.update(self.headers)
    
    def visit_base_site(self, exchange):
        """Visit the base website to get cookies"""
        print(f"Visiting {exchange} base site to get cookies...")
        try:
            if exchange == "BSE":
                # Visit BSE homepage
                response = self.bse_session.get(self.bse_base_url, timeout=30)
                if response.status_code == 200:
                    print(f"Successfully visited {exchange} base site")
                    # Cookie dicts intentionally NOT logged — they include
                    # session tokens that would land in publicly-readable CI logs.
                    time.sleep(self.delay)
                    return True
            else:  # NSE
                # Visit NSE homepage first
                response = self.nse_session.get(self.nse_base_url, timeout=30)
                if response.status_code == 200:
                    print(f"Successfully visited {exchange} homepage")
                    # Also visit the reports page to get proper session
                    reports_url = f"{self.nse_base_url}/all-reports"
                    response = self.nse_session.get(reports_url, timeout=30)
                    if response.status_code == 200:
                        print(f"Successfully visited {exchange} reports page")
                        # Cookies intentionally NOT logged — see BSE branch above.
                        time.sleep(self.delay)
                        return True
            
            print(f"Failed to visit {exchange} base site: {response.status_code}")
            return False
        except Exception as e:
            print(f"Error visiting {exchange} base site: {e}")
            return False
    
    def download_bse_report(self, date):
        """Download BSE MTF report for a specific date.

        BSE switched URL/format on 2025-10-03:
          - <= 2025-10-01: https://www.bseindia.com/markets/downloads/MarginTrading_DDMMYYYY.xls
          - >= 2025-10-03: https://www.bseindia.com/downloads/Margin/MarginTrading_DDMMYYYY.csv
        We try the new path first, fall back to the old path. On failure we re-visit
        the BSE homepage to refresh cookies and retry once.
        """
        date_str = date.strftime("%d%m%Y")
        new_url = f"{self.bse_base_url}/downloads/Margin/MarginTrading_{date_str}.csv"
        old_url = f"{self.bse_base_url}/markets/downloads/MarginTrading_{date_str}.xls"
        new_filepath = os.path.join(self.bse_dir, f"BSE_MTF_{date_str}.csv")
        old_filepath = os.path.join(self.bse_dir, f"BSE_MTF_{date_str}.xls")

        if os.path.exists(new_filepath) or os.path.exists(old_filepath):
            print(f"BSE report for {date_str} already exists, skipping...")
            return True

        referer = f"{self.bse_base_url}/markets/equity/EQReports/MarginTrading.aspx"
        headers = {'Referer': referer}

        def _try(url, dst, expected_ct_keywords):
            try:
                r = self.bse_session.get(url, headers=headers, timeout=30)
                ct = r.headers.get('content-type', '').lower()
                if r.status_code == 200 and any(k in ct for k in expected_ct_keywords) and len(r.content) > 1000:
                    with open(dst, 'wb') as f:
                        f.write(r.content)
                    return True, r.status_code, ct, len(r.content)
                return False, r.status_code, ct, len(r.content)
            except Exception as e:
                return False, 'ERR', str(e), 0

        print(f"Downloading BSE report for {date_str}...")
        # 1st attempt: new CSV path
        ok, st, ct, sz = _try(new_url, new_filepath, ['octet-stream', 'csv'])
        if ok:
            print(f"  Successfully downloaded BSE (csv) for {date_str}")
            return True
        # 2nd attempt: old XLS path
        ok, st2, ct2, sz2 = _try(old_url, old_filepath, ['excel', 'octet-stream'])
        if ok:
            print(f"  Successfully downloaded BSE (xls) for {date_str}")
            return True

        # Both failed — refresh cookies by re-visiting the homepage, then retry the new URL once.
        try:
            self.bse_session.get(self.bse_base_url, timeout=30)
            self.bse_session.get(referer, timeout=30)
        except Exception as e:
            print(f"  cookie refresh failed: {e}")

        ok, st3, ct3, sz3 = _try(new_url, new_filepath, ['octet-stream', 'csv'])
        if ok:
            print(f"  Successfully downloaded BSE (csv, retry) for {date_str}")
            return True
        ok, st4, ct4, sz4 = _try(old_url, old_filepath, ['excel', 'octet-stream'])
        if ok:
            print(f"  Successfully downloaded BSE (xls, retry) for {date_str}")
            return True

        print(f"  BSE report not available for {date_str} (csv:{st}/{sz}B xls:{st2}/{sz2}B retry-csv:{st3}/{sz3}B retry-xls:{st4}/{sz4}B)")
        return False
    
    def download_nse_report(self, date):
        """Download NSE MTF report for a specific date"""
        date_str = date.strftime("%d-%b-%Y")
        url = f"{self.nse_base_url}/api/reports?archives=[{{%22name%22:%22CM%20-%20Margin%20Trading%20Disclosure%22,%22type%22:%22archives%22,%22category%22:%22capital-market%22,%22section%22:%22equities%22}}]&date={date_str}&type=equities&mode=single"
        
        date_compact = date.strftime('%d%m%Y')
        filename = f"NSE_MTF_{date_compact}.csv"
        filepath = os.path.join(self.nse_dir, filename)
        zip_filepath = os.path.join(self.nse_dir, f"NSE_MTF_{date_compact}.zip")

        if os.path.exists(filepath) or os.path.exists(zip_filepath):
            print(f"NSE report for {date_str} already exists, skipping...")
            return True
        
        try:
            print(f"Downloading NSE report for {date_str}...")
            
            # NSE requires specific headers
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.nseindia.com/all-reports',
            }
            
            response = self.nse_session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Check if response is JSON or direct file download
                content_type = response.headers.get('content-type', '')
                
                if 'application/json' in content_type:
                    # NSE returns JSON with download link
                    try:
                        data = response.json()
                        if data and len(data) > 0 and 'link' in data[0]:
                            download_url = data[0]['link']
                            
                            # Download the actual file
                            file_response = self.nse_session.get(download_url, timeout=30)
                            if file_response.status_code == 200:
                                with open(filepath, 'wb') as f:
                                    f.write(file_response.content)
                                print(f"Successfully downloaded NSE report for {date_str}")
                                return True
                            else:
                                print(f"Failed to download NSE file for {date_str}")
                                return False
                        else:
                            print(f"NSE report not available for {date_str}")
                            return False
                    except ValueError:
                        print(f"Invalid JSON response from NSE for {date_str}")
                        return False
                else:
                    # Direct file download (CSV/ZIP)
                    if len(response.content) > 0:
                        # Change extension to .zip if it's a zip file
                        if response.content[:2] == b'PK':
                            filepath = filepath.replace('.csv', '.zip')
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        print(f"Successfully downloaded NSE report for {date_str}")
                        return True
                    else:
                        print(f"Empty response from NSE for {date_str}")
                        return False
            else:
                print(f"NSE report not available for {date_str} (Status: {response.status_code})")
                return False
        except Exception as e:
            print(f"Error downloading NSE report for {date_str}: {e}")
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
    parser = argparse.ArgumentParser(description="Download MTF reports from BSE and NSE")
    parser.add_argument("--start-year", type=int, default=2011, help="Start year (default: 2011)")
    parser.add_argument("--start-month", type=int, default=1, help="Start month (default: 1)")
    parser.add_argument("--end-year", type=int, default=datetime.now().year, help="End year (default: current year)")
    parser.add_argument("--exchange", choices=["BSE", "NSE", "both"], default="both", help="Exchange to download from")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests in seconds (default: 2)")
    parser.add_argument("--output-dir", default="mtf_reports", help="Output directory (default: mtf_reports)")
    parser.add_argument("--month", type=int, help="Download specific month (1-12)")
    parser.add_argument("--year", type=int, help="Download specific year")
    parser.add_argument("--last-days", type=int, help="Download last n days")
    
    args = parser.parse_args()
    
    downloader = MTFDownloader(output_dir=args.output_dir, delay=args.delay)
    
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
        print(f"Downloading reports from {args.start_month}/{args.start_year} to {args.end_year}...")
        for year in range(args.start_year, args.end_year + 1):
            print(f"\nProcessing year {year}...")
            if year == args.start_year:
                # For start year, begin from specified month
                start_date = datetime(year, args.start_month, 1)
                end_date = datetime(year, 12, 31)
                if year == datetime.now().year:
                    end_date = datetime.now()
                downloader.download_all_reports(start_date, end_date, args.exchange)
            else:
                # For other years, download the entire year
                downloader.download_year(year, args.exchange)
            time.sleep(downloader.delay * 2)  # Extra delay between years

if __name__ == "__main__":
    main()