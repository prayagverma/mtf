# MTF Report Downloader

This script downloads Margin Trading Facility (MTF) reports from both NSE and BSE exchanges.

## Features

- Downloads MTF reports from BSE (Excel format) and NSE (CSV format)
- Supports downloading from 2011 onwards
- Implements rate limiting for respectful downloading
- Maintains session cookies for proper authentication
- Skips already downloaded files
- Handles weekends automatically

## Requirements

```bash
pip install requests
```

## Usage

### Download all reports from 2011 to current year
```bash
python3 mtf_downloader.py
```

### Download reports for a specific year
```bash
python3 mtf_downloader.py --year 2023
```

### Download reports for a specific month
```bash
python3 mtf_downloader.py --year 2023 --month 6
```

### Download last N days
```bash
python3 mtf_downloader.py --last-days 30
```

### Download from specific exchange only
```bash
python3 mtf_downloader.py --exchange BSE
python3 mtf_downloader.py --exchange NSE
```

### Custom date range
```bash
python3 mtf_downloader.py --start-year 2020 --end-year 2023
```

### Adjust download delay (default 2 seconds)
```bash
python3 mtf_downloader.py --delay 5
```

## Output Structure

Reports are saved in the following structure:
```
mtf_reports/
├── BSE/
│   ├── BSE_MTF_01012023.xls
│   ├── BSE_MTF_02012023.xls
│   └── ...
└── NSE/
    ├── NSE_MTF_01012023.csv
    ├── NSE_MTF_02012023.csv
    └── ...
```

## URL Patterns

- BSE: `https://www.bseindia.com/markets/downloads/MarginTrading_DDMMYYYY.xls`
- NSE: Uses API endpoint with date in DD-MMM-YYYY format

## Notes

- NSE requires authentication which may cause 401 errors
- BSE reports are in Excel (.xls) format
- NSE reports are in CSV format
- The script visits base websites first to establish cookies
- Weekends are automatically skipped