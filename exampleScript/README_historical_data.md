# Historical Weather Data Fetching

This script fetches historical weather data from the NOAA Climate Data Online (CDO) API for use in the Ray training pipeline.

## Setup

### 1. Get NOAA CDO API Token

1. Visit: https://www.ncei.noaa.gov/cdo-web/token
2. Sign up or log in
3. Copy your personal token
4. Replace `YOUR_PERSONAL_NCEI_TOKEN` in `getHistoricaldata.py`

### 2. Configure Stations

Edit the `STATIONS` list in `getHistoricaldata.py` to include the stations you want:

```python
STATIONS = [
    {
        "id": "GHCND:USW00014837",  # Station ID (GHCND format)
        "name": "Madison_Dane_County"  # Friendly name for filenames
    },
    # Add more stations...
]
```

**Finding Station IDs:**
- Visit: https://www.ncei.noaa.gov/cdo-web/datasets
- Search for stations in your area
- Use the GHCND (Global Historical Climatology Network - Daily) dataset
- Copy the station ID (format: `GHCND:USW00014837`)

### 3. Configure Date Range

Edit the date range in the `if __name__ == "__main__":` section:

```python
END_DATE = datetime(2023, 12, 31)
START_DATE = datetime(2020, 1, 1)  # Adjust as needed
```

**Note:** The CDO API has limits:
- 1000 records per request
- 5 requests per second (rate limiting)
- The script automatically chunks large date ranges

## Usage

### Run Locally

```bash
# From project root
python3 exampleScript/getHistoricaldata.py
```

### Run in Docker (if needed)

```bash
# If you need to run in a container with network access
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  python:3.9 \
  python3 exampleScript/getHistoricaldata.py
```

## Output

### File Structure

Data is saved to: `src/data/historical/`

```
src/data/historical/
├── Madison_Dane_County_2020-01-01_to_2020-12-31_chunk001.json
├── Madison_Dane_County_2020-01-01_to_2020-12-31_chunk002.json
├── ...
└── Madison_Dane_County_2020-01-01_to_2023-12-31.json  # Combined file
```

### File Format

Each JSON file contains:

```json
{
  "metadata": {
    "station_name": "Madison_Dane_County",
    "start_date": "2020-01-01",
    "end_date": "2020-12-31",
    "record_count": 1825,
    "fetched_at": "2025-12-13T10:30:00Z",
    "chunk_index": 1
  },
  "records": [
    {
      "date": "2020-01-01T00:00:00",
      "datatype": "TMAX",
      "station": "GHCND:USW00014837",
      "value": 5.6,
      "attributes": "0,0,2400"
    },
    {
      "date": "2020-01-01T00:00:00",
      "datatype": "TMIN",
      "station": "GHCND:USW00014837",
      "value": -2.3,
      "attributes": "0,0,2400"
    },
    ...
  ]
}
```

### Data Types Retrieved

- **TMAX**: Maximum Temperature (°C)
- **TMIN**: Minimum Temperature (°C)
- **PRCP**: Precipitation (mm)
- **AWND**: Average Wind Speed (m/s)
- **WSFG**: Peak Wind Gust (m/s)
- **RHUM**: Relative Humidity (%)

## Next Steps

After fetching historical data:

1. **Review the data:**
   ```bash
   # Check file sizes
   ls -lh src/data/historical/
   
   # Preview a file
   head -50 src/data/historical/Madison_Dane_County_2020-01-01_to_2020-12-31.json
   ```

2. **Use in Ray Training:**
   - The data will be loaded by `src/ray/training/data_loader.py`
   - The loader will parse JSON files and convert to training format
   - Data will be preprocessed and split into train/validation/test sets

3. **Train Models:**
   ```bash
   # After implementing training scripts
   python3 src/ray/training/train_forecasting.py
   python3 src/ray/training/train_anomaly.py
   ```

## Troubleshooting

### "HTTP Error: 401"
- Your NOAA token is invalid or expired
- Get a new token from: https://www.ncei.noaa.gov/cdo-web/token

### "HTTP Error: 400"
- Check that station IDs are valid
- Verify date range is within available data
- Some stations may not have data for all date ranges

### "No records retrieved"
- Station may not have data for the specified date range
- Try a different date range or station
- Check station availability at: https://www.ncei.noaa.gov/cdo-web/datasets

### Rate Limiting
- The script includes delays between requests
- If you hit rate limits, increase `REQUEST_DELAY_SECONDS` in the script

## API Limits

- **1000 records per request** (handled automatically by chunking)
- **5 requests per second** (handled by delays)
- **1000 station-years per day** (for free tier)

For large datasets, consider:
- Fetching data in smaller batches
- Using multiple API tokens (if allowed)
- Using the paid API tier for higher limits

## References

- NOAA CDO API Documentation: https://www.ncei.noaa.gov/cdo-web/webservices/v2
- Station Search: https://www.ncei.noaa.gov/cdo-web/datasets
- API Token: https://www.ncei.noaa.gov/cdo-web/token

