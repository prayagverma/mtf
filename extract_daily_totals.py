#!/usr/bin/env python3
import os
import pandas as pd
import zipfile
from datetime import datetime
import json

def extract_nse_totals(filepath, date):
    """Extract totals from NSE MTF file"""
    try:
        # Extract CSV from zip
        with zipfile.ZipFile(filepath, 'r') as z:
            csv_name = z.namelist()[0]
            csv_content = z.read(csv_name).decode('utf-8')
        
        lines = csv_content.split('\n')
        
        # Parse header section for totals
        totals = {
            'date': date.strftime('%Y-%m-%d'),
            'exchange': 'NSE',
            'beginning_outstanding': None,
            'fresh_exposure': None,
            'exposure_liquidated': None,
            'end_outstanding': None,
            'securities_count': 0
        }
        
        # Count securities
        in_data = False
        for line in lines:
            if 'Symbol,Name,Qty Fin by all the members' in line:
                in_data = True
                continue
            if in_data and line.strip() and ',' in line:
                totals['securities_count'] += 1
        
        # Extract summary values
        for line in lines[:20]:  # Summary is in first 20 lines
            if 'Total Outstanding on the beginning' in line or 'Scripwise Total Outstanding on the beginning' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        # Try to extract the numeric value
                        value_str = parts[2].strip()
                        # Remove any non-numeric characters except . and -
                        value_str = ''.join(c for c in value_str if c.isdigit() or c in '.-')
                        if value_str:
                            totals['beginning_outstanding'] = float(value_str)
                    except:
                        pass
            elif 'Fresh Exposure taken during the day' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        value_str = parts[2].strip()
                        value_str = ''.join(c for c in value_str if c.isdigit() or c in '.-')
                        if value_str:
                            totals['fresh_exposure'] = float(value_str)
                    except:
                        pass
            elif 'Exposure liquidated during the day' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        value_str = parts[2].strip()
                        value_str = ''.join(c for c in value_str if c.isdigit() or c in '.-')
                        if value_str:
                            totals['exposure_liquidated'] = float(value_str)
                    except:
                        pass
            elif 'Net scripwise outstanding at the end' in line or 'Net outstanding at the end' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        value_str = parts[2].strip()
                        value_str = ''.join(c for c in value_str if c.isdigit() or c in '.-')
                        if value_str:
                            totals['end_outstanding'] = float(value_str)
                    except:
                        pass
        
        return totals
        
    except Exception as e:
        print(f"Error processing NSE file {filepath}: {e}")
        return None

def extract_bse_totals(filepath, date):
    """Extract totals from BSE MTF file"""
    try:
        # Read the raw file to get the total line
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Also read as dataframe to get row count
        df = pd.read_csv(filepath, sep='\t')
        
        # Remove any "Total" rows that might be included in the DataFrame
        df = df[df['scripname'].astype(str).str.lower() != 'total'].copy()
        df = df.dropna(subset=['scrip_code'])  # Remove any rows without scrip_code
        
        totals = {
            'date': date.strftime('%Y-%m-%d'),
            'exchange': 'BSE',
            'amount_financed': None,
            'beginning_outstanding': None,
            'exposure_taken': None,
            'exposure_liquidated': None,
            'end_outstanding': None,
            'securities_count': len(df)
        }
        
        # Find the total line (usually last line)
        total_line_found = False
        for line in reversed(all_lines):
            if 'Total' in line or 'TOTAL' in line:
                parts = line.strip().split('\t')
                if len(parts) >= 8:
                    try:
                        # Skip first two columns (code and name), then parse the numeric values
                        totals['amount_financed'] = float(parts[3]) if parts[3] else None
                        totals['beginning_outstanding'] = float(parts[4]) if parts[4] else None
                        totals['exposure_taken'] = float(parts[5]) if parts[5] else None
                        totals['exposure_liquidated'] = float(parts[6]) if parts[6] else None
                        totals['end_outstanding'] = float(parts[7]) if parts[7] else None
                        total_line_found = True
                        print(f"Found BSE total line: end_outstanding={totals['end_outstanding']}")
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If no total line found, calculate from data (but don't double-count)
        if not total_line_found:
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            if 'Financed by Members AMOUNT_FINANCED' in numeric_cols:
                totals['amount_financed'] = df['Financed by Members AMOUNT_FINANCED'].sum()
            if 'TO_BOD' in numeric_cols:
                totals['beginning_outstanding'] = df['TO_BOD'].sum()
            if 'ET_DD' in numeric_cols:
                totals['exposure_taken'] = df['ET_DD'].sum()
            if 'EL_DD' in numeric_cols:
                totals['exposure_liquidated'] = df['EL_DD'].sum()
            if 'NO_EOD' in numeric_cols:
                totals['end_outstanding'] = df['NO_EOD'].sum()
            print(f"Calculated BSE totals: end_outstanding={totals['end_outstanding']}")
        
        # The total line already contains the correct totals, so we use those
        # Note: BSE provides totals at the end of each file
        
        return totals
        
    except Exception as e:
        print(f"Error processing BSE file {filepath}: {e}")
        return None

def main():
    """Extract daily totals from all MTF files"""
    
    print("EXTRACTING DAILY TOTALS FROM MTF FILES")
    print("=" * 80)
    
    all_totals = []
    
    # Process NSE files
    nse_dir = "mtf_reports/NSE"
    if os.path.exists(nse_dir):
        nse_files = sorted([f for f in os.listdir(nse_dir) if f.endswith('.zip')])
        print(f"\nProcessing {len(nse_files)} NSE files...")
        
        for i, filename in enumerate(nse_files):
            if i % 100 == 0:
                print(f"  Processing NSE file {i+1}/{len(nse_files)}...")
            
            filepath = os.path.join(nse_dir, filename)
            date_str = filename.replace('NSE_MTF_', '').replace('.zip', '')
            
            try:
                date = datetime.strptime(date_str, '%d%m%Y')
                totals = extract_nse_totals(filepath, date)
                if totals:
                    all_totals.append(totals)
            except:
                pass
    
    # Process BSE files
    bse_dir = "mtf_reports/BSE"
    if os.path.exists(bse_dir):
        bse_files = sorted([f for f in os.listdir(bse_dir) if f.endswith('.xls')])
        print(f"\nProcessing {len(bse_files)} BSE files...")
        
        for i, filename in enumerate(bse_files):
            if i % 100 == 0:
                print(f"  Processing BSE file {i+1}/{len(bse_files)}...")
            
            filepath = os.path.join(bse_dir, filename)
            date_str = filename.replace('BSE_MTF_', '').replace('.xls', '')
            
            try:
                date = datetime.strptime(date_str, '%d%m%Y')
                totals = extract_bse_totals(filepath, date)
                if totals:
                    all_totals.append(totals)
            except:
                pass
    
    # Sort by date and exchange
    all_totals.sort(key=lambda x: (x['date'], x['exchange']))
    
    # Save to CSV
    df = pd.DataFrame(all_totals)
    output_file = "mtf_daily_totals.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n" + "=" * 80)
    print(f"EXTRACTION COMPLETE")
    print(f"Total records extracted: {len(all_totals)}")
    print(f"NSE records: {len([t for t in all_totals if t['exchange'] == 'NSE'])}")
    print(f"BSE records: {len([t for t in all_totals if t['exchange'] == 'BSE'])}")
    print(f"Output saved to: {output_file}")
    
    # Also save as JSON for easier reading
    json_output = "mtf_daily_totals.json"
    with open(json_output, 'w') as f:
        json.dump(all_totals, f, indent=2)
    print(f"JSON output saved to: {json_output}")
    
    # Show sample of the data
    print(f"\nSAMPLE DATA (first 5 records):")
    print(df.head().to_string(index=False))
    
    print(f"\nSAMPLE DATA (last 5 records):")
    print(df.tail().to_string(index=False))
    
    # Basic statistics
    print(f"\n" + "=" * 80)
    print("BASIC STATISTICS")
    print("=" * 80)
    
    # NSE stats
    nse_df = df[df['exchange'] == 'NSE']
    if not nse_df.empty:
        print("\nNSE Statistics (Rs. in Lakhs):")
        print(f"  Average End Outstanding: {nse_df['end_outstanding'].mean():,.2f}")
        print(f"  Max End Outstanding: {nse_df['end_outstanding'].max():,.2f}")
        print(f"  Min End Outstanding: {nse_df['end_outstanding'].min():,.2f}")
        print(f"  Average Securities Count: {nse_df['securities_count'].mean():.0f}")
    
    # BSE stats
    bse_df = df[df['exchange'] == 'BSE']
    if not bse_df.empty:
        print("\nBSE Statistics (Rs. in Lakhs):")
        print(f"  Average End Outstanding: {bse_df['end_outstanding'].mean():,.2f}")
        print(f"  Max End Outstanding: {bse_df['end_outstanding'].max():,.2f}")
        print(f"  Min End Outstanding: {bse_df['end_outstanding'].min():,.2f}")
        print(f"  Average Securities Count: {bse_df['securities_count'].mean():.0f}")

if __name__ == "__main__":
    main()