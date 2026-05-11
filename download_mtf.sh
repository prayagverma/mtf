#!/bin/bash

# Download MTF reports from Feb 2011 onwards
# Run in background with nohup to avoid timeout

echo "Starting MTF download from Feb 2011..."
echo "Logs will be saved to mtf_download.log"

nohup python3 mtf_downloader.py --start-year 2011 --start-month 2 --delay 3 > mtf_download.log 2>&1 &

echo "Download started in background with PID: $!"
echo "Check progress with: tail -f mtf_download.log"