#!/usr/bin/env python3
import os
import pandas as pd
import zipfile
from datetime import datetime
import json
import re

def select_best_csv(csv_files):
    """Select the best CSV file when multiple exist"""
    if len(csv_files) == 1:
        return csv_files[0]
    
    # Prefer non-provisional files
    non_provisional = [f for f in csv_files if 'provisional' not in f.lower()]
    if non_provisional:
        # If multiple non-provisional, prefer shorter names (usually final files)
        return min(non_provisional, key=len)
    
    # If all are provisional, take the first one
    return csv_files[0]

def extract_value_from_line(line, search_term):
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

def extract_nse_totals(filepath, date):
    """Extract totals from NSE MTF file with robust parsing for all formats"""
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            # Find CSV files (might be nested in directories)
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                print(f"No CSV found in {filepath}")
                return None
            
            # Select the best CSV file
            csv_file = select_best_csv(csv_files)
            csv_content = z.read(csv_file).decode('utf-8', errors='ignore')
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
        
        # Search for values in first 30 lines with flexible parsing
        for line in lines[:30]:
            if 'Outstanding on the beginning' in line or 'Total Outstanding on the beginning' in line:
                value = extract_value_from_line(line, 'Outstanding on the beginning')
                if value is not None and totals['beginning_outstanding'] is None:
                    totals['beginning_outstanding'] = value
                    
            elif 'Fresh Exposure taken' in line:
                value = extract_value_from_line(line, 'Fresh Exposure taken')
                if value is not None and totals['fresh_exposure'] is None:
                    totals['fresh_exposure'] = value
                    
            elif 'Exposure liquidated' in line:
                value = extract_value_from_line(line, 'Exposure liquidated')
                if value is not None and totals['exposure_liquidated'] is None:
                    totals['exposure_liquidated'] = value
                    
            elif 'outstanding at the end' in line or 'Net outstanding at the end' in line:
                value = extract_value_from_line(line, 'outstanding at the end')
                if value is not None and totals['end_outstanding'] is None:
                    totals['end_outstanding'] = value
        
        # Count securities
        in_data = False
        for line in lines:
            if 'Symbol,Name,Qty Fin' in line:
                in_data = True
                continue
            if in_data and line.strip():
                # Check if it's a data line
                parts = line.split(',')
                if len(parts) >= 3:
                    # First part should be a symbol (not empty, not starting with comma)
                    symbol = parts[0].strip()
                    if symbol and not symbol.startswith(',') and symbol != '':
                        # Exclude totals, notes, and numeric codes
                        if ('Total' not in symbol and 'TOTAL' not in symbol and 
                            'Figures are rounded' not in symbol and
                            '*' not in symbol):
                            # Check if it looks like a valid symbol
                            if not symbol.isdigit() and len(symbol) > 0:
                                totals['securities_count'] += 1
        
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
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If no total line found, calculate from data
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
        
        return totals
        
    except Exception as e:
        print(f"Error processing BSE file {filepath}: {e}")
        return None

def main():
    """Extract daily totals from all MTF files with final fix for multi-CSV issues"""
    
    print("EXTRACTING DAILY TOTALS FROM MTF FILES (FINAL FIX - HANDLES MULTI-CSV)")
    print("=" * 80)
    
    all_totals = []
    
    # Process NSE files
    nse_dir = "mtf_reports/NSE"
    if os.path.exists(nse_dir):
        nse_files = sorted([f for f in os.listdir(nse_dir) if f.endswith('.zip')])
        print(f"\nProcessing {len(nse_files)} NSE files...")
        
        blank_count = 0
        success_count = 0
        
        for i, filename in enumerate(nse_files):
            if i % 500 == 0:
                print(f"  Processing NSE file {i+1}/{len(nse_files)}...")
            
            filepath = os.path.join(nse_dir, filename)
            date_str = filename.replace('NSE_MTF_', '').replace('.zip', '')
            
            try:
                date = datetime.strptime(date_str, '%d%m%Y')
                totals = extract_nse_totals(filepath, date)
                if totals:
                    if totals['end_outstanding'] is None:
                        blank_count += 1
                        if date_str == '13092022':  # Debug the specific problem file
                            print(f"  Still blank after fix: {filename}")
                    else:
                        success_count += 1
                    all_totals.append(totals)
            except Exception as e:
                print(f"Error with {filename}: {e}")
        
        print(f"\n  NSE Processing Summary:")
        print(f"    Successfully extracted: {success_count}")
        print(f"    Files with blank totals: {blank_count}")
    
    # Process BSE files
    bse_dir = "mtf_reports/BSE"
    if os.path.exists(bse_dir):
        bse_files = sorted([f for f in os.listdir(bse_dir) if f.endswith('.xls')])
        print(f"\nProcessing {len(bse_files)} BSE files...")
        
        for i, filename in enumerate(bse_files):
            if i % 200 == 0:
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
    output_file = "mtf_daily_totals_final.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n" + "=" * 80)
    print(f"EXTRACTION COMPLETE")
    print(f"Total records extracted: {len(all_totals)}")
    print(f"NSE records: {len([t for t in all_totals if t['exchange'] == 'NSE'])}")
    print(f"BSE records: {len([t for t in all_totals if t['exchange'] == 'BSE'])}")
    print(f"Output saved to: {output_file}")
    
    # Also create version in crores
    monetary_columns = [
        'beginning_outstanding',
        'fresh_exposure',
        'exposure_liquidated', 
        'end_outstanding',
        'amount_financed',
        'exposure_taken'
    ]
    
    df_crores = df.copy()
    for col in monetary_columns:
        if col in df_crores.columns:
            df_crores[col] = df_crores[col].apply(lambda x: round(x/100, 2) if pd.notna(x) else None)
    
    crores_file = "mtf_daily_totals_final_crores.csv"
    df_crores.to_csv(crores_file, index=False)
    print(f"Crores version saved to: {crores_file}")
    
    # Test the specific problematic date
    sep_13_data = df[df['date'] == '2022-09-13']
    if not sep_13_data.empty:
        print(f"\n📊 September 13, 2022 data:")
        print(sep_13_data[['date', 'exchange', 'end_outstanding', 'securities_count']].to_string(index=False))
    
    # Check for any remaining blanks
    nse_df = df[df['exchange'] == 'NSE']
    blank_nse = nse_df[nse_df['end_outstanding'].isna()]
    if not blank_nse.empty:
        print(f"\n⚠️  WARNING: {len(blank_nse)} NSE records still have blank end_outstanding values")
    else:
        print(f"\n✅ All NSE records successfully extracted!")

if __name__ == "__main__":
    main()