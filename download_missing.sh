#!/bin/bash

echo "Downloading missing MTF reports..."

# Download NSE 2015 (continue from where it stopped)
echo "Downloading NSE 2015..."
nohup python3 mtf_downloader.py --year 2015 --exchange NSE --delay 2 > nse_2015.log 2>&1 &
echo "NSE 2015 download started (PID: $!)"

# Wait a bit before starting next
sleep 5

# Download NSE 2024
echo "Downloading NSE 2024..."
nohup python3 mtf_downloader.py --year 2024 --exchange NSE --delay 2 > nse_2024.log 2>&1 &
echo "NSE 2024 download started (PID: $!)"

# Wait a bit before starting next
sleep 5

# Download BSE 2019
echo "Downloading BSE 2019..."
nohup python3 mtf_downloader.py --year 2019 --exchange BSE --delay 2 > bse_2019.log 2>&1 &
echo "BSE 2019 download started (PID: $!)"

# Wait a bit before starting next
sleep 5

# Download BSE 2020
echo "Downloading BSE 2020..."
nohup python3 mtf_downloader.py --year 2020 --exchange BSE --delay 2 > bse_2020.log 2>&1 &
echo "BSE 2020 download started (PID: $!)"

echo "All downloads started in background. Check logs:"
echo "  tail -f nse_2015.log"
echo "  tail -f nse_2024.log"
echo "  tail -f bse_2019.log"
echo "  tail -f bse_2020.log"