#!/usr/bin/env python3
import pandas as pd
import json

def lakhs_to_crores(value):
    """Convert lakhs to crores"""
    if pd.isna(value) or value is None:
        return None
    return round(value / 100, 2)

def main():
    # Read the CSV file
    df = pd.read_csv('mtf_daily_totals.csv')
    
    # List of columns that contain monetary values in lakhs
    monetary_columns = [
        'beginning_outstanding',
        'fresh_exposure',
        'exposure_liquidated', 
        'end_outstanding',
        'amount_financed',
        'exposure_taken'
    ]
    
    # Convert each monetary column from lakhs to crores
    for col in monetary_columns:
        if col in df.columns:
            df[col] = df[col].apply(lakhs_to_crores)
    
    # Save to CSV
    output_csv = 'mtf_daily_totals_crores.csv'
    df.to_csv(output_csv, index=False)
    print(f"CSV file saved: {output_csv}")
    
    # Also save as JSON for easier reading
    json_data = df.to_dict('records')
    json_output = 'mtf_daily_totals_crores.json'
    with open(json_output, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"JSON file saved: {json_output}")
    
    # Print summary statistics
    print("\n" + "="*80)
    print("MTF DAILY TOTALS IN CRORES")
    print("="*80)
    
    # Show sample data
    print("\nFirst 5 records:")
    print(df.head().to_string(index=False))
    
    print("\nLast 5 records:")
    print(df.tail().to_string(index=False))
    
    # Statistics by exchange
    print("\n" + "="*80)
    print("STATISTICS (in Crores)")
    print("="*80)
    
    for exchange in ['NSE', 'BSE']:
        exchange_df = df[df['exchange'] == exchange]
        if not exchange_df.empty:
            print(f"\n{exchange} Statistics:")
            print(f"  Total records: {len(exchange_df)}")
            
            # Date range
            try:
                dates = pd.to_datetime(exchange_df['date'], format='%d-%m-%Y')
            except:
                try:
                    dates = pd.to_datetime(exchange_df['date'], format='%Y-%m-%d')
                except:
                    dates = pd.to_datetime(exchange_df['date'], format='mixed')
            print(f"  Date range: {dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}")
            
            # End outstanding stats
            if 'end_outstanding' in exchange_df.columns:
                end_outstanding = exchange_df['end_outstanding'].dropna()
                if not end_outstanding.empty:
                    print(f"\n  End Outstanding (Rs. Crores):")
                    print(f"    Average: {end_outstanding.mean():,.2f}")
                    print(f"    Median:  {end_outstanding.median():,.2f}")
                    print(f"    Min:     {end_outstanding.min():,.2f}")
                    print(f"    Max:     {end_outstanding.max():,.2f}")
                    print(f"    Latest:  {end_outstanding.iloc[-1]:,.2f}")
            
            # Securities count
            if 'securities_count' in exchange_df.columns:
                securities = exchange_df['securities_count'].dropna()
                if not securities.empty:
                    print(f"\n  Securities Count:")
                    print(f"    Average: {securities.mean():.0f}")
                    print(f"    Latest:  {securities.iloc[-1]:.0f}")
    
    # Growth analysis for recent data
    print("\n" + "="*80)
    print("RECENT TRENDS (August-September 2025)")
    print("="*80)
    
    recent_df = df[df['date'] >= '2025-08-01']
    
    for exchange in ['NSE', 'BSE']:
        exchange_recent = recent_df[recent_df['exchange'] == exchange]
        if len(exchange_recent) > 1 and 'end_outstanding' in exchange_recent.columns:
            end_outstanding = exchange_recent['end_outstanding'].dropna()
            if len(end_outstanding) > 1:
                first_value = end_outstanding.iloc[0]
                last_value = end_outstanding.iloc[-1]
                change = last_value - first_value
                pct_change = (change / first_value) * 100
                
                print(f"\n{exchange} (Aug-Sep 2025):")
                print(f"  Start Outstanding: {first_value:,.2f} Cr")
                print(f"  End Outstanding:   {last_value:,.2f} Cr")
                print(f"  Change:            {change:+,.2f} Cr ({pct_change:+.2f}%)")

if __name__ == "__main__":
    main()