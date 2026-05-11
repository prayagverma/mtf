#!/usr/bin/env python3
import zipfile
import re
from datetime import datetime

def extract_value_from_line(line, search_term):
    """Extract numeric value from a line containing the search term"""
    if search_term not in line:
        return None
    
    # Split by comma and look for numeric values
    parts = line.split(',')
    
    # Try to find a numeric value in the parts
    for part in parts:
        # Clean the part
        cleaned = part.strip()
        # Remove any non-numeric characters except . and -
        cleaned = re.sub(r'[^\d.-]', '', cleaned)
        
        # Check if it's a valid number and looks like a large value (in lakhs)
        if cleaned and '.' in cleaned:
            try:
                value = float(cleaned)
                # MTF values are typically large (in lakhs), so filter out small numbers
                if value > 1000:  # At least 1000 lakhs
                    return value
            except:
                continue
    
    return None

def extract_nse_totals_robust(filepath, date):
    """Extract totals from NSE MTF file with robust parsing"""
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            # Find CSV files
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                return None
            
            csv_content = z.read(csv_files[0]).decode('utf-8', errors='ignore')
            lines = csv_content.split('\n')
        
        totals = {
            'date': date.strftime('%Y-%m-%d'),
            'exchange': 'NSE',
            'beginning_outstanding': None,
            'fresh_exposure': None,
            'exposure_liquidated': None,
            'end_outstanding': None,
            'securities_count': 0
        }
        
        # Search for values in first 30 lines
        for line in lines[:30]:
            if 'Outstanding on the beginning' in line:
                value = extract_value_from_line(line, 'Outstanding on the beginning')
                if value:
                    totals['beginning_outstanding'] = value
                    
            elif 'Fresh Exposure taken' in line:
                value = extract_value_from_line(line, 'Fresh Exposure taken')
                if value:
                    totals['fresh_exposure'] = value
                    
            elif 'Exposure liquidated' in line:
                value = extract_value_from_line(line, 'Exposure liquidated')
                if value:
                    totals['exposure_liquidated'] = value
                    
            elif 'outstanding at the end' in line:
                value = extract_value_from_line(line, 'outstanding at the end')
                if value:
                    totals['end_outstanding'] = value
        
        # Count securities
        in_data = False
        for line in lines:
            if 'Symbol,Name,Qty Fin' in line:
                in_data = True
                continue
            if in_data and line.strip():
                # Check if it's a data line (not empty, not a total)
                parts = line.split(',')
                if len(parts) >= 3 and parts[0].strip() and not parts[0].strip().startswith(','):
                    if 'Total' not in parts[0] and parts[0].strip() != '':
                        totals['securities_count'] += 1
        
        return totals
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None

# Test on problematic files
test_files = [
    ('mtf_reports/NSE/NSE_MTF_01092025.zip', '01092025'),
    ('mtf_reports/NSE/NSE_MTF_06112021.zip', '06112021'),
    ('mtf_reports/NSE/NSE_MTF_25082025.zip', '25082025'),
    ('mtf_reports/NSE/NSE_MTF_01082025.zip', '01082025'),  # A working file for comparison
]

print("Testing robust extraction on problematic files:")
print("="*60)

for filepath, date_str in test_files:
    date = datetime.strptime(date_str, '%d%m%Y')
    result = extract_nse_totals_robust(filepath, date)
    
    print(f"\nFile: {filepath}")
    if result:
        print(f"  Beginning: {result['beginning_outstanding']}")
        print(f"  Fresh: {result['fresh_exposure']}")
        print(f"  Liquidated: {result['exposure_liquidated']}")
        print(f"  End: {result['end_outstanding']}")
        print(f"  Securities: {result['securities_count']}")
    else:
        print("  Failed to extract")