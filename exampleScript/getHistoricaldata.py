import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import time

# --- Configuration ---

# **IMPORTANT**: Replace with your actual NOAA NCEI Token
# Get your token from: https://www.ncei.noaa.gov/cdo-web/token
NOAA_TOKEN = "qqshCfOaNvYeOsIONKWdgintvyxXohGJ" 

# Base URL for the Climate Data Online (CDO) API v2
BASE_URL = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"

# Example station IDs (GHCND format)
# You can find station IDs at: https://www.ncei.noaa.gov/cdo-web/datasets
STATIONS = [
    {
        "id": "GHCND:USW00014837",  # Dane County Regional Airport, Madison, WI
        "name": "Madison_Dane_County"
    },
    {
        "id": "GHCND:USW00014839",  # Milwaukee Mitchell International Airport
        "name": "Milwaukee_Mitchell"
    },
    {
        "id": "GHCND:USW00094846",  # Chicago O'Hare International Airport
        "name": "Chicago_OHare"
    },
    {
        "id": "GHCND:USW00014922",  # Minneapolis-St. Paul International Airport
        "name": "Minneapolis_StPaul"
    },
    {
        "id": "GHCND:USW00094982",  # Des Moines International Airport
        "name": "Des_Moines"
    },
]

# Dataset to query: Global Historical Climatology Network - Daily
DATASET_ID = "GHCND" 

# Data Types (Variables) to retrieve:
# TMAX = Maximum Temperature (C), TMIN = Minimum Temperature (C), PRCP = Precipitation (mm)
# AWND = Average Wind Speed (m/s), WSFG = Peak Wind Gust (m/s)
# RHUM = Relative Humidity (%)
DATATYPE_IDS = "TMAX,TMIN,PRCP,AWND,WSFG,RHUM" 

# Output directory for saved data
OUTPUT_DIR = Path("src/data/historical")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# API request settings
MAX_RECORDS_PER_REQUEST = 1000  # CDO API limit
REQUEST_DELAY_SECONDS = 0.5  # Delay between requests to avoid rate limiting


# --- Functions ---

def fetch_cdo_historical_data(start_date: str, end_date: str, station_id: str) -> list:
    """
    Fetches historical data for a single station over a constrained time period.
    Returns list of records or empty list on error.
    """
    headers = {
        'token': NOAA_TOKEN
    }
    
    params = {
        'datasetid': DATASET_ID,
        'stationid': station_id,
        'datatypeid': DATATYPE_IDS,
        'startdate': start_date,
        'enddate': end_date,
        'units': 'metric',  # Requesting metric units (Celsius, mm, m/s)
        'limit': MAX_RECORDS_PER_REQUEST,
    }
    
    print(f"  Requesting data for {station_id} from {start_date} to {end_date}...")
    
    try:
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status() 
        data = response.json()
        
        # The actual records are stored in the 'results' array
        records = data.get('results', [])
        print(f"  ✓ Retrieved {len(records)} records")
        return records
        
    except requests.exceptions.HTTPError as e:
        print(f"\n  ✗ HTTP Error: {e}")
        if response.status_code == 401:
            print("  → Check your NOAA_TOKEN - it may be invalid or expired")
        elif response.status_code == 400:
            print(f"  → Response: {response.text[:200]}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request failed: {e}")
        return []
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return []


def chunk_date_range(start_date: datetime, end_date: datetime, days_per_chunk: int = 365) -> list:
    """
    Splits a date range into smaller chunks to handle API limits.
    Returns list of (start, end) datetime tuples.
    """
    chunks = []
    current_start = start_date
    
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=days_per_chunk), end_date)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    
    return chunks


def save_data_to_file(data: list, station_name: str, start_date: str, end_date: str, chunk_index: int = None) -> Path:
    """
    Saves historical data to a JSON file.
    Returns the path to the saved file.
    """
    # Create filename with station name and date range
    if chunk_index is not None:
        filename = f"{station_name}_{start_date}_to_{end_date}_chunk{chunk_index:03d}.json"
    else:
        filename = f"{station_name}_{start_date}_to_{end_date}.json"
    
    filepath = OUTPUT_DIR / filename
    
    # Save data as JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'station_name': station_name,
                'start_date': start_date,
                'end_date': end_date,
                'record_count': len(data),
                'fetched_at': datetime.utcnow().isoformat() + 'Z',
                'chunk_index': chunk_index
            },
            'records': data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved {len(data)} records to {filepath}")
    return filepath


def fetch_and_save_station_data(station: dict, start_date: datetime, end_date: datetime, days_per_chunk: int = 365) -> dict:
    """
    Fetches all historical data for a station across the date range and saves to files.
    Returns summary statistics.
    """
    station_id = station['id']
    station_name = station['name']
    
    print(f"\n{'='*80}")
    print(f"Processing Station: {station_name} ({station_id})")
    print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"{'='*80}")
    
    # Split date range into chunks
    date_chunks = chunk_date_range(start_date, end_date, days_per_chunk)
    print(f"Split into {len(date_chunks)} chunk(s) of ~{days_per_chunk} days each")
    
    all_records = []
    saved_files = []
    
    for chunk_idx, (chunk_start, chunk_end) in enumerate(date_chunks, 1):
        start_str = chunk_start.strftime('%Y-%m-%d')
        end_str = chunk_end.strftime('%Y-%m-%d')
        
        # Fetch data for this chunk
        records = fetch_cdo_historical_data(start_str, end_str, station_id)
        
        if records:
            # Save chunk to file
            filepath = save_data_to_file(records, station_name, start_str, end_str, chunk_idx)
            saved_files.append(str(filepath))
            all_records.extend(records)
        
        # Rate limiting: delay between requests
        if chunk_idx < len(date_chunks):
            time.sleep(REQUEST_DELAY_SECONDS)
    
    # Also save a combined file for convenience
    if all_records:
        combined_filepath = save_data_to_file(
            all_records, 
            station_name, 
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d')
        )
        saved_files.append(str(combined_filepath))
    
    return {
        'station_name': station_name,
        'station_id': station_id,
        'total_records': len(all_records),
        'files_saved': len(saved_files),
        'file_paths': saved_files,
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    }


def print_summary(summaries: list):
    """Prints a summary of all fetched data."""
    print(f"\n{'='*80}")
    print("FETCH SUMMARY")
    print(f"{'='*80}")
    
    total_records = sum(s['total_records'] for s in summaries)
    total_files = sum(s['files_saved'] for s in summaries)
    
    print(f"\nTotal Stations Processed: {len(summaries)}")
    print(f"Total Records Fetched: {total_records:,}")
    print(f"Total Files Saved: {total_files}")
    print(f"\nOutput Directory: {OUTPUT_DIR.absolute()}")
    
    print(f"\n{'='*80}")
    print("Per-Station Summary:")
    print(f"{'='*80}")
    
    for summary in summaries:
        print(f"\n{summary['station_name']} ({summary['station_id']}):")
        print(f"  Records: {summary['total_records']:,}")
        print(f"  Files: {summary['files_saved']}")
        print(f"  Date Range: {summary['date_range']['start']} to {summary['date_range']['end']}")
        if summary['file_paths']:
            print(f"  First File: {Path(summary['file_paths'][0]).name}")
            if len(summary['file_paths']) > 1:
                print(f"  Last File: {Path(summary['file_paths'][-1]).name}")


# --- Main Execution ---

if __name__ == "__main__":
    
    # Validate token
    if NOAA_TOKEN == "YOUR_PERSONAL_NCEI_TOKEN":
        print("=" * 80)
        print("ERROR: Please set your NOAA_TOKEN in the script!")
        print("Get your token from: https://www.ncei.noaa.gov/cdo-web/token")
        print("=" * 80)
        exit(1)
    
    print("=" * 80)
    print("NOAA CDO Historical Data Fetch (Batch Layer for Training)")
    print("=" * 80)
    print(f"\nOutput Directory: {OUTPUT_DIR.absolute()}")
    print(f"Stations to Process: {len(STATIONS)}")
    print(f"Data Types: {DATATYPE_IDS}")
    
    # Configuration: Date range to fetch
    # Adjust these dates based on your training data needs
    # Note: CDO API has limits (e.g., 1000 records per request, 5 requests per second)
    END_DATE = datetime(2023, 12, 31)
    START_DATE = datetime(2020, 1, 1)  # ~4 years of data
    
    # Days per chunk: Adjust based on how many records per day you expect
    # For daily data, 365 days = ~365 records per chunk (well under 1000 limit)
    # For hourly data, you'd need much smaller chunks
    DAYS_PER_CHUNK = 365
    
    print(f"\nDate Range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    print(f"Days per Chunk: {DAYS_PER_CHUNK}")
    print(f"\nStarting data fetch...\n")
    
    # Process each station
    summaries = []
    for station in STATIONS:
        try:
            summary = fetch_and_save_station_data(
                station, 
                START_DATE, 
                END_DATE, 
                days_per_chunk=DAYS_PER_CHUNK
            )
            summaries.append(summary)
        except Exception as e:
            print(f"\n✗ Error processing station {station['name']}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Print final summary
    if summaries:
        print_summary(summaries)
        print(f"\n{'='*80}")
        print("✓ Data fetch completed successfully!")
        print(f"{'='*80}")
        print(f"\nNext Steps:")
        print(f"1. Review the saved JSON files in: {OUTPUT_DIR.absolute()}")
        print(f"2. Use these files in your Ray training pipeline:")
        print(f"   - src/ray/training/data_loader.py")
        print(f"3. The data format is JSON with 'metadata' and 'records' fields")
        print(f"4. Each record contains: date, station, datatype, value, attributes")
    else:
        print(f"\n✗ No data was fetched. Please check your configuration and token.")
        print(f"  - Verify NOAA_TOKEN is correct")
        print(f"  - Check station IDs are valid")
        print(f"  - Verify date range is within available data")
