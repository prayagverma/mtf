#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os

def visualize_mtf_trends():
    """Create visualizations of MTF daily totals"""
    
    # Load the data
    if not os.path.exists('mtf_daily_totals.csv'):
        print("Error: mtf_daily_totals.csv not found. Run extract_daily_totals.py first.")
        return
    
    df = pd.read_csv('mtf_daily_totals.csv')
    df['date'] = pd.to_datetime(df['date'])
    
    # Separate NSE and BSE data
    nse_df = df[df['exchange'] == 'NSE'].copy()
    bse_df = df[df['exchange'] == 'BSE'].copy()
    
    # Sort by date
    nse_df = nse_df.sort_values('date')
    bse_df = bse_df.sort_values('date')
    
    # Create figure with subplots
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle('MTF (Margin Trading Facility) Daily Trends', fontsize=16)
    
    # 1. End Outstanding Trends
    ax = axes[0, 0]
    ax.plot(nse_df['date'], nse_df['end_outstanding']/100000, label='NSE', color='blue', alpha=0.7)
    ax.plot(bse_df['date'], bse_df['end_outstanding']/100000, label='BSE', color='red', alpha=0.7)
    ax.set_ylabel('Outstanding (Rs. Thousand Crores)')
    ax.set_title('Daily End Outstanding')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Securities Count
    ax = axes[0, 1]
    ax.plot(nse_df['date'], nse_df['securities_count'], label='NSE', color='blue', alpha=0.7)
    ax.plot(bse_df['date'], bse_df['securities_count'], label='BSE', color='red', alpha=0.7)
    ax.set_ylabel('Number of Securities')
    ax.set_title('Securities in MTF')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Daily Activity (NSE)
    ax = axes[1, 0]
    ax.plot(nse_df['date'], nse_df['fresh_exposure']/1000, label='Fresh Exposure', color='green', alpha=0.7)
    ax.plot(nse_df['date'], nse_df['exposure_liquidated']/1000, label='Exposure Liquidated', color='orange', alpha=0.7)
    ax.set_ylabel('Amount (Rs. Crores)')
    ax.set_title('NSE Daily Activity')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Daily Activity (BSE)
    ax = axes[1, 1]
    ax.plot(bse_df['date'], bse_df['exposure_taken']/1000, label='Exposure Taken', color='green', alpha=0.7)
    ax.plot(bse_df['date'], bse_df['exposure_liquidated']/1000, label='Exposure Liquidated', color='orange', alpha=0.7)
    ax.set_ylabel('Amount (Rs. Crores)')
    ax.set_title('BSE Daily Activity')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 5. Year-wise Average Outstanding
    ax = axes[2, 0]
    nse_yearly = nse_df.groupby(nse_df['date'].dt.year)['end_outstanding'].mean()/100000
    bse_yearly = bse_df.groupby(bse_df['date'].dt.year)['end_outstanding'].mean()/100000
    
    years = sorted(set(nse_yearly.index) | set(bse_yearly.index))
    x = range(len(years))
    width = 0.35
    
    ax.bar([i - width/2 for i in x], [nse_yearly.get(y, 0) for y in years], width, label='NSE', color='blue', alpha=0.7)
    ax.bar([i + width/2 for i in x], [bse_yearly.get(y, 0) for y in years], width, label='BSE', color='red', alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(years, rotation=45)
    ax.set_ylabel('Avg Outstanding (Rs. Thousand Crores)')
    ax.set_title('Year-wise Average Outstanding')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 6. Growth Rate
    ax = axes[2, 1]
    # Calculate 30-day moving average
    nse_df['ma30'] = nse_df['end_outstanding'].rolling(window=30).mean()
    bse_df['ma30'] = bse_df['end_outstanding'].rolling(window=30).mean()
    
    # Calculate YoY growth
    nse_df['yoy_growth'] = (nse_df['ma30'] / nse_df['ma30'].shift(252) - 1) * 100
    bse_df['yoy_growth'] = (bse_df['ma30'] / bse_df['ma30'].shift(252) - 1) * 100
    
    ax.plot(nse_df['date'], nse_df['yoy_growth'], label='NSE YoY Growth', color='blue', alpha=0.7)
    ax.plot(bse_df['date'], bse_df['yoy_growth'], label='BSE YoY Growth', color='red', alpha=0.7)
    ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
    ax.set_ylabel('YoY Growth (%)')
    ax.set_title('Year-over-Year Growth Rate')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Format x-axis for all subplots
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # Save the plot
    output_file = 'mtf_trends_visualization.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Visualization saved to: {output_file}")
    
    # Create summary statistics
    print("\n" + "="*80)
    print("MTF SUMMARY STATISTICS")
    print("="*80)
    
    # NSE Summary
    print("\nNSE SUMMARY:")
    print(f"  Period: {nse_df['date'].min().strftime('%d-%b-%Y')} to {nse_df['date'].max().strftime('%d-%b-%Y')}")
    print(f"  Total Trading Days: {len(nse_df)}")
    print(f"  Current Outstanding: Rs. {nse_df.iloc[-1]['end_outstanding']:,.2f} Lakhs")
    print(f"  Peak Outstanding: Rs. {nse_df['end_outstanding'].max():,.2f} Lakhs on {nse_df.loc[nse_df['end_outstanding'].idxmax(), 'date'].strftime('%d-%b-%Y')}")
    print(f"  Average Daily Fresh Exposure: Rs. {nse_df['fresh_exposure'].mean():,.2f} Lakhs")
    print(f"  Average Securities Count: {nse_df['securities_count'].mean():.0f}")
    
    # BSE Summary
    print("\nBSE SUMMARY:")
    print(f"  Period: {bse_df['date'].min().strftime('%d-%b-%Y')} to {bse_df['date'].max().strftime('%d-%b-%Y')}")
    print(f"  Total Trading Days: {len(bse_df)}")
    print(f"  Current Outstanding: Rs. {bse_df.iloc[-1]['end_outstanding']:,.2f} Lakhs")
    print(f"  Peak Outstanding: Rs. {bse_df['end_outstanding'].max():,.2f} Lakhs on {bse_df.loc[bse_df['end_outstanding'].idxmax(), 'date'].strftime('%d-%b-%Y')}")
    print(f"  Average Daily Exposure Taken: Rs. {bse_df['exposure_taken'].mean():,.2f} Lakhs")
    print(f"  Average Securities Count: {bse_df['securities_count'].mean():.0f}")
    
    # Growth Analysis
    print("\nGROWTH ANALYSIS:")
    nse_start = nse_df.iloc[0]['end_outstanding']
    nse_end = nse_df.iloc[-1]['end_outstanding']
    nse_growth = (nse_end / nse_start - 1) * 100
    
    print(f"  NSE Total Growth: {nse_growth:.1f}% ({nse_df.iloc[0]['date'].year} to {nse_df.iloc[-1]['date'].year})")
    
    if len(bse_df) > 0:
        bse_start = bse_df.iloc[0]['end_outstanding']
        bse_end = bse_df.iloc[-1]['end_outstanding']
        bse_growth = (bse_end / bse_start - 1) * 100
        print(f"  BSE Total Growth: {bse_growth:.1f}% ({bse_df.iloc[0]['date'].year} to {bse_df.iloc[-1]['date'].year})")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    visualize_mtf_trends()