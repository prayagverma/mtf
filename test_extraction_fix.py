#!/usr/bin/env python3
import zipfile
import re

def extract_value_from_line_fixed(line, search_term):
    """Extract numeric value from a line, skipping line numbers"""
    if search_term not in line:
        return None
    
    parts = line.split(',')
    
    # Find the part with the search term
    search_part_index = -1
    for i, part in enumerate(parts):
        if search_term in part:
            search_part_index = i
            break
    
    # Look for numeric values AFTER the search term part
    for i in range(search_part_index + 1, len(parts)):
        part = parts[i].strip()
        # Remove any non-numeric characters except . and -
        cleaned = re.sub(r'[^\d.-]', '', part)
        
        if cleaned and ('.' in cleaned or cleaned.isdigit()):
            try:
                value = float(cleaned)
                # Accept the first valid number after the search term
                if value >= 0:
                    return value
            except:
                continue
    
    return None

# Test on the problematic file
filepath = 'mtf_reports/NSE/NSE_MTF_13092022.zip'

with zipfile.ZipFile(filepath, 'r') as z:
    csv_files = [f for f in z.namelist() if f.endswith('.csv')]
    
    # Select non-provisional file
    final_file = [f for f in csv_files if 'provisional' not in f.lower()][0]
    print(f"Testing fixed extraction on: {final_file}")
    
    csv_content = z.read(final_file).decode('utf-8', errors='ignore')
    lines = csv_content.split('\n')
    
    print("\nExtracted values:")
    
    for line in lines[:10]:
        if 'Outstanding on the beginning' in line:
            value = extract_value_from_line_fixed(line, 'Outstanding on the beginning')
            print(f"Beginning Outstanding: {value}")
            
        elif 'Fresh Exposure taken' in line:
            value = extract_value_from_line_fixed(line, 'Fresh Exposure taken')
            print(f"Fresh Exposure: {value}")
            
        elif 'Exposure liquidated' in line:
            value = extract_value_from_line_fixed(line, 'Exposure liquidated')
            print(f"Exposure Liquidated: {value}")
            
        elif 'outstanding at the end' in line:
            value = extract_value_from_line_fixed(line, 'outstanding at the end')
            print(f"End Outstanding: {value}")

print("\n" + "="*50)
print("EXPECTED VALUES:")
print("Beginning Outstanding: 2471941.93")
print("Fresh Exposure: 233646.46")  
print("Exposure Liquidated: 235978.51")
print("End Outstanding: 2469609.88")