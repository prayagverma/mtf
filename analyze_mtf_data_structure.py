#!/usr/bin/env python3
import zipfile
import pandas as pd
import os
from datetime import datetime

def analyze_nse_file(filepath):
    """Analyze NSE MTF file structure"""
    print("NSE MTF FILE ANALYSIS")
    print("=" * 50)
    
    # Extract CSV from zip
    with zipfile.ZipFile(filepath, 'r') as z:
        csv_name = z.namelist()[0]
        csv_content = z.read(csv_name).decode('utf-8')
    
    lines = csv_content.split('\n')
    
    print(f"File: {os.path.basename(filepath)}")
    print(f"Contains: {csv_name}")
    print(f"Total lines: {len(lines)}")
    
    # Parse the structure
    header_section = []
    data_section = []
    in_data = False
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
            
        if 'Symbol,Name,Qty Fin by all the members' in line:
            in_data = True
            data_header = line
            continue
            
        if not in_data:
            header_section.append(line)
        else:
            if line.strip() and ',' in line:
                data_section.append(line)
    
    print(f"\nHEADER SECTION ({len(header_section)} lines):")
    for line in header_section[:10]:
        print(f"  {line}")
    
    print(f"\nDATA SECTION:")
    print(f"  Header: {data_header}")
    print(f"  Data rows: {len(data_section)}")
    
    # Parse data section
    if data_section:
        print(f"\nSAMPLE DATA (first 5 rows):")
        for line in data_section[:5]:
            parts = line.split(',')
            if len(parts) >= 4:
                symbol = parts[0]
                name = parts[1]
                qty = parts[2]
                amount = parts[3]
                print(f"  {symbol:<12} | {name:<30} | {qty:<15} | {amount:<15}")
    
    # Extract summary data
    summary_data = {}
    for line in header_section:
        if 'Total Outstanding on the beginning' in line:
            parts = line.split(',')
            if len(parts) >= 3:
                summary_data['Beginning Outstanding'] = parts[2].strip()
        elif 'Fresh Exposure taken during the day' in line:
            parts = line.split(',')
            if len(parts) >= 3:
                summary_data['Fresh Exposure'] = parts[2].strip()
        elif 'Exposure liquidated during the day' in line:
            parts = line.split(',')
            if len(parts) >= 3:
                summary_data['Exposure Liquidated'] = parts[2].strip()
        elif 'Net scripwise outstanding at the end' in line:
            parts = line.split(',')
            if len(parts) >= 3:
                summary_data['End Outstanding'] = parts[2].strip()
    
    print(f"\nSUMMARY DATA:")
    for key, value in summary_data.items():
        print(f"  {key}: {value} lakhs")
    
    return {
        'type': 'NSE',
        'format': 'ZIP containing CSV',
        'summary_data': summary_data,
        'securities_count': len(data_section),
        'data_columns': ['Symbol', 'Name', 'Qty Financed (Shares)', 'Amount Financed (Rs. Lakhs)']
    }

def analyze_bse_file(filepath):
    """Analyze BSE MTF file structure"""
    print("\n\nBSE MTF FILE ANALYSIS")
    print("=" * 50)
    
    print(f"File: {os.path.basename(filepath)}")
    
    # Read the raw file to check for totals at the end
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        all_lines = f.readlines()
    
    # Read as tab-separated file
    try:
        df = pd.read_csv(filepath, sep='\t')
        
        print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        
        print(f"\nCOLUMNS:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")
        
        print(f"\nCOLUMN MEANINGS:")
        column_meanings = {
            'scrip_code': 'BSE Security Code',
            'scripname': 'Company Name',
            'Financed by Members QUANTITY_FINANCED': 'Quantity Financed (Shares)',
            'Financed by Members AMOUNT_FINANCED': 'Amount Financed (Rs. Lakhs)',
            'TO_BOD': 'Total Outstanding Beginning of Day',
            'ET_DD': 'Exposure Taken During Day',
            'EL_DD': 'Exposure Liquidated During Day',
            'NO_EOD': 'Net Outstanding End of Day'
        }
        
        for col in df.columns:
            meaning = column_meanings.get(col, 'Unknown')
            print(f"  {col}: {meaning}")
        
        print(f"\nSAMPLE DATA (first 5 rows):")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(df.head().to_string(index=False))
        
        # Check for totals at the end of the file
        print(f"\n📊 TOTALS AT END OF FILE:")
        total_lines = []
        for line in all_lines[-10:]:  # Check last 10 lines
            if 'Total' in line or 'TOTAL' in line:
                total_lines.append(line.strip())
        
        if total_lines:
            print("BSE files contain TOTAL row at the end with summary data:")
            for line in total_lines:
                print(f"  {line}")
            
            # Parse the total line if it exists
            if len(all_lines) > len(df) + 1:  # Header + data rows + total row
                total_line = all_lines[-1].strip()
                if '\t' in total_line:
                    total_parts = total_line.split('\t')
                    if len(total_parts) >= 8:
                        print(f"\nPARSED TOTALS FROM FILE:")
                        print(f"  Total Quantity Financed: {total_parts[2]} shares")
                        print(f"  Total Amount Financed: {total_parts[3]} lakhs")
                        print(f"  Total Outstanding BOD: {total_parts[4]} lakhs")
                        print(f"  Total Exposure Taken: {total_parts[5]} lakhs")
                        print(f"  Total Exposure Liquidated: {total_parts[6]} lakhs")
                        print(f"  Total Outstanding EOD: {total_parts[7]} lakhs")
        else:
            # Calculate totals from data
            numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
            totals = df[numeric_columns].sum()
            
            print(f"\nCALCULATED TOTALS FROM DATA:")
            for col in numeric_columns:
                if 'AMOUNT' in col or col in ['TO_BOD', 'ET_DD', 'EL_DD', 'NO_EOD']:
                    print(f"  {col}: {totals[col]:.2f} lakhs")
                else:
                    print(f"  {col}: {totals[col]:,.0f} shares")
        
        return {
            'type': 'BSE',
            'format': 'Tab-separated text file (.xls extension)',
            'securities_count': len(df),
            'data_columns': list(df.columns),
            'has_total_row': len(total_lines) > 0
        }
        
    except Exception as e:
        print(f"Error reading BSE file: {e}")
        return None

def compare_data_points(nse_analysis, bse_analysis):
    """Compare NSE and BSE data points"""
    print("\n\n" + "="*80)
    print("MTF DATA STRUCTURE COMPARISON")
    print("="*80)
    
    print(f"\nFILE FORMATS:")
    print(f"  NSE: {nse_analysis['format']}")
    print(f"  BSE: {bse_analysis['format']}")
    
    print(f"\nDATA VOLUME:")
    print(f"  NSE: {nse_analysis['securities_count']} securities")
    print(f"  BSE: {bse_analysis['securities_count']} securities")
    
    print(f"\nKEY DATA POINTS:")
    
    print(f"\n🎯 NSE DATA POINTS:")
    print(f"  1. Daily Summary Metrics:")
    for key, value in nse_analysis['summary_data'].items():
        print(f"     - {key}: {value} lakhs")
    
    print(f"  2. Security-wise Details:")
    for i, col in enumerate(nse_analysis['data_columns'], 1):
        print(f"     - {col}")
    
    print(f"\n🎯 BSE DATA POINTS:")
    print(f"  1. Security-wise Detailed Breakdown:")
    for i, col in enumerate(bse_analysis['data_columns'], 1):
        meaning = {
            'scrip_code': 'Security Code',
            'scripname': 'Company Name', 
            'Financed by Members QUANTITY_FINANCED': 'Total Quantity Financed',
            'Financed by Members AMOUNT_FINANCED': 'Total Amount Financed',
            'TO_BOD': 'Outstanding at Beginning of Day',
            'ET_DD': 'New Exposure During Day',
            'EL_DD': 'Exposure Closed During Day', 
            'NO_EOD': 'Net Outstanding at End of Day'
        }.get(col, col)
        print(f"     {i}. {col} ({meaning})")
    
    if bse_analysis.get('has_total_row'):
        print(f"\n  2. Summary Totals (at end of file):")
        print(f"     - Total row with aggregate values for all securities")
        print(f"     - Market-wide totals for each metric")
    
    print(f"\n📊 DATA RICHNESS COMPARISON:")
    print(f"  NSE provides:")
    print(f"    ✅ Market-level summary statistics")
    print(f"    ✅ Security-wise outstanding positions")
    print(f"    ✅ Simple 4-column structure")
    
    print(f"  BSE provides:")
    print(f"    ✅ Detailed intraday movement tracking")
    print(f"    ✅ Beginning/end of day positions")
    print(f"    ✅ Daily exposure changes")
    print(f"    ✅ Richer 8-column structure")
    print(f"    ✅ Total summary row at file end")
    
    print(f"\n🎯 MAIN DATA POINTS SUMMARY:")
    print(f"  Both exchanges track:")
    print(f"    • Company/Security identification")
    print(f"    • Quantity financed (number of shares)")
    print(f"    • Amount financed (in Rs. Lakhs)")
    print(f"    • Outstanding positions")
    
    print(f"  BSE additionally tracks:")
    print(f"    • Intraday position changes")
    print(f"    • Beginning vs end of day positions")
    print(f"    • Daily exposure movements")

def main():
    """Main analysis function"""
    # Select sample files
    nse_file = "mtf_reports/NSE/NSE_MTF_01012024.zip"
    bse_file = "mtf_reports/BSE/BSE_MTF_01012024.xls"
    
    if not os.path.exists(nse_file):
        print(f"NSE file not found: {nse_file}")
        return
    
    if not os.path.exists(bse_file):
        print(f"BSE file not found: {bse_file}")
        return
    
    # Analyze both files
    nse_analysis = analyze_nse_file(nse_file)
    bse_analysis = analyze_bse_file(bse_file)
    
    if nse_analysis and bse_analysis:
        compare_data_points(nse_analysis, bse_analysis)
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()