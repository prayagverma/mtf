#!/usr/bin/env python3
"""
Compress stock analytics data for efficient static website serving
Reduces 600MB+ JSON to manageable chunks with multiple optimization strategies
"""

import json
import gzip
import os
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockDataCompressor:
    def __init__(self):
        self.stock_data = None
        
    def load_data(self, input_file):
        """Load the large JSON file"""
        logger.info(f"Loading {input_file}...")
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        logger.info(f"Original file size: {file_size_mb:.2f} MB")
        
        with open(input_file, 'r') as f:
            self.stock_data = json.load(f)
        
        logger.info(f"Loaded data for {len(self.stock_data.get('daily_stock_data', {}))} stocks")
        
    def optimize_data_structure(self):
        """Optimize the data structure to reduce redundancy"""
        optimized_data = {
            'metadata': {
                'version': '2.0',
                'compressed': True,
                'extraction_date': self.stock_data.get('extraction_date'),
                'time_series_summary': self.stock_data.get('time_series_summary'),
                'total_stock_records': self.stock_data.get('total_stock_records')
            },
            'latest_snapshot': {
                'nse_stocks': self.stock_data.get('nse_stocks'),
                'bse_stocks': self.stock_data.get('bse_stocks'),
                'combined_stocks': self.stock_data.get('combined_stocks'),
                'sudden_changes': self.stock_data.get('sudden_changes'),
                'cross_exchange_stocks': self.stock_data.get('cross_exchange_stocks'),
                'active_securities': self.stock_data.get('active_securities'),
            },
            'stock_index': {},  # Quick lookup index
            'compressed_daily_data': {}  # Compressed time-series
        }
        
        # Process daily stock data with compression
        daily_data = self.stock_data.get('daily_stock_data', {})
        
        for symbol, records in daily_data.items():
            if not records or len(records) == 0:
                continue
                
            # Create stock index entry
            first_record = records[0]
            last_record = records[-1]
            
            optimized_data['stock_index'][symbol] = {
                'name': last_record.get('name', symbol),
                'exchange': last_record.get('exchange', 'BSE'),
                'record_count': len(records),
                'date_range': {
                    'start': first_record.get('date'),
                    'end': last_record.get('date')
                },
                'latest_amount': last_record.get('amount_financed', 0)
            }
            
            # Compress time-series data
            compressed_records = self.compress_time_series(records)
            optimized_data['compressed_daily_data'][symbol] = compressed_records
            
        return optimized_data
    
    def compress_time_series(self, records):
        """Compress time-series data by removing redundancy and using arrays"""
        if not records:
            return []
            
        # Extract unique keys from first record
        first_record = records[0]
        
        # Define which fields to keep (remove redundant fields)
        essential_fields = [
            'date',
            'amount_financed',
            'qty_financed',
            'avg_price'
        ]
        
        # Additional fields for BSE
        bse_fields = [
            'beginning_outstanding',
            'end_outstanding',
            'exposure_taken',
            'exposure_liquidated'
        ]
        
        # Check if this is BSE data
        is_bse = 'beginning_outstanding' in first_record
        
        if is_bse:
            fields = essential_fields + bse_fields
        else:
            fields = essential_fields + ['beginning_amount', 'fresh_amount']
        
        # Convert to column-based format (much more efficient)
        compressed = {
            'fields': fields,
            'data': []
        }
        
        for record in records:
            row = []
            for field in fields:
                value = record.get(field)
                # Round floats to 2 decimal places to save space
                if isinstance(value, float):
                    value = round(value, 2)
                row.append(value)
            compressed['data'].append(row)
            
        return compressed
    
    def create_data_chunks(self, optimized_data, chunk_size_mb=50):
        """Split data into manageable chunks"""
        chunks = []
        
        # Always include metadata and snapshot in first chunk
        base_chunk = {
            'metadata': optimized_data['metadata'],
            'latest_snapshot': optimized_data['latest_snapshot'],
            'stock_index': optimized_data['stock_index'],
            'chunk_info': {
                'total_chunks': 0,
                'chunk_number': 0
            }
        }
        
        # Estimate base chunk size
        base_size = len(json.dumps(base_chunk))
        
        # Create stock data chunks
        current_chunk = {'stocks': {}}
        current_size = 0
        chunk_number = 1
        
        for symbol, data in optimized_data['compressed_daily_data'].items():
            data_size = len(json.dumps({symbol: data}))
            
            if current_size + data_size > chunk_size_mb * 1024 * 1024:
                # Save current chunk
                chunks.append({
                    'chunk_info': {
                        'chunk_number': chunk_number,
                        'type': 'stock_data'
                    },
                    'stocks': current_chunk['stocks']
                })
                
                # Start new chunk
                current_chunk = {'stocks': {}}
                current_size = 0
                chunk_number += 1
            
            current_chunk['stocks'][symbol] = data
            current_size += data_size
        
        # Add last chunk
        if current_chunk['stocks']:
            chunks.append({
                'chunk_info': {
                    'chunk_number': chunk_number,
                    'type': 'stock_data'
                },
                'stocks': current_chunk['stocks']
            })

        # Update base chunk with total chunks info
        base_chunk['chunk_info']['total_chunks'] = len(chunks) + 1

        # Annotate each stock_index entry with the chunk it lives in. This
        # lets the dashboard fetch exactly one ~8 MB chunk when the user
        # opens a stock detail chart, instead of sequentially fetching
        # chunks 1..N until the symbol is found (worst case 5x slower).
        for i, ck in enumerate(chunks, 1):
            for symbol in (ck.get('stocks') or {}).keys():
                if symbol in base_chunk['stock_index']:
                    base_chunk['stock_index'][symbol]['chunk_number'] = i

        return base_chunk, chunks
    
    def save_compressed_files(self, optimized_data, output_dir='compressed_data'):
        """Save compressed files with gzip"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Create chunks
        base_chunk, data_chunks = self.create_data_chunks(optimized_data)
        
        # Save base file (contains metadata, index, and latest snapshot)
        base_file = os.path.join(output_dir, 'stock_analytics_base.json.gz')
        with gzip.open(base_file, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(base_chunk, f, separators=(',', ':'))
        
        base_size = os.path.getsize(base_file) / (1024 * 1024)
        logger.info(f"Base file size: {base_size:.2f} MB")
        
        # Save data chunks
        total_chunk_size = 0
        for i, chunk in enumerate(data_chunks):
            chunk_file = os.path.join(output_dir, f'stock_data_chunk_{i+1}.json.gz')
            with gzip.open(chunk_file, 'wt', encoding='utf-8', compresslevel=9) as f:
                json.dump(chunk, f, separators=(',', ':'))
            
            chunk_size = os.path.getsize(chunk_file) / (1024 * 1024)
            total_chunk_size += chunk_size
            logger.info(f"Chunk {i+1} size: {chunk_size:.2f} MB")
        
        # Create a manifest file
        manifest = {
            'version': '2.0',
            'created': datetime.now().isoformat(),
            'base_file': 'stock_analytics_base.json.gz',
            'chunks': [f'stock_data_chunk_{i+1}.json.gz' for i in range(len(data_chunks))],
            'total_stocks': len(optimized_data['stock_index']),
            'compression_stats': {
                'original_size_mb': 612,
                'compressed_size_mb': base_size + total_chunk_size,
                'compression_ratio': round((base_size + total_chunk_size) / 612 * 100, 2)
            }
        }
        
        manifest_file = os.path.join(output_dir, 'manifest.json')
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"\nCompression complete!")
        logger.info(f"Original size: 612 MB")
        logger.info(f"Compressed size: {base_size + total_chunk_size:.2f} MB")
        logger.info(f"Compression ratio: {manifest['compression_stats']['compression_ratio']:.1f}%")
        logger.info(f"Files saved to: {output_dir}/")
        
        return manifest
    
    def create_single_compressed_file(self, optimized_data, output_file='stock_analytics_compressed.json.gz'):
        """Create a single compressed file as an alternative"""
        logger.info("Creating single compressed file...")
        
        # Remove daily_stock_data from the original structure to avoid duplication
        output_data = {
            'metadata': optimized_data['metadata'],
            'latest_snapshot': optimized_data['latest_snapshot'],
            'stock_index': optimized_data['stock_index'],
            'compressed_daily_data': optimized_data['compressed_daily_data']
        }
        
        with gzip.open(output_file, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(output_data, f, separators=(',', ':'))
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"Single compressed file size: {file_size:.2f} MB")
        
        return output_file, file_size

def main():
    compressor = StockDataCompressor()
    
    # Load original data
    compressor.load_data('stock_analytics.json')
    
    # Optimize data structure
    logger.info("Optimizing data structure...")
    optimized_data = compressor.optimize_data_structure()
    
    # Save compressed chunks (for progressive loading)
    logger.info("\nCreating compressed chunks for progressive loading...")
    manifest = compressor.save_compressed_files(optimized_data)
    
    # Also create a single compressed file
    logger.info("\nCreating single compressed file...")
    single_file, single_size = compressor.create_single_compressed_file(
        optimized_data, 
        'compressed_data/stock_analytics_full.json.gz'
    )
    
    print("\n" + "="*60)
    print("COMPRESSION SUMMARY")
    print("="*60)
    print(f"Original file: 612 MB")
    print(f"Single compressed file: {single_size:.2f} MB")
    print(f"Chunked files: {manifest['compression_stats']['compressed_size_mb']:.2f} MB total")
    print(f"Compression achieved: {100 - manifest['compression_stats']['compression_ratio']:.1f}% reduction")
    print("\nRecommended approach:")
    print("- Use chunked files for progressive loading")
    print("- Load base file first (contains index + latest data)")
    print("- Load individual chunks on-demand when user requests specific stocks")

if __name__ == "__main__":
    main()