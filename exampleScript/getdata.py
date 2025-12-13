# This script get data from the NWS API and format it for the Kafka topic
import requests
import json
from datetime import datetime

# --- Configuration ---
# 1. Location for your "station"
# Example: Madison, WI (your current context location)
LATITUDE = 43.0731
LONGITUDE = -89.4012

# 2. Required User-Agent Header
# Replace with your project name and contact info
USER_AGENT = "MyKafkaRayWeatherProject/1.0 (ultimateStreamandDistribute_kafka-spark-ray, jsun424@wisc.edu)" 
BASE_URL = "https://api.weather.gov"

# --- Functions ---

def fetch_nws_hourly_forecast(lat: float, lon: float) -> list:
    """
    Fetches the 7-day hourly forecast from the NWS API in a two-step process.
    Returns a list of hourly forecast periods.
    """
    # 1. Prepare Headers
    headers = {
        'User-Agent': USER_AGENT,
        # NWS strongly recommends accepting this GeoJSON format
        'Accept': 'application/geo+json' 
    }
    
    # 2. STEP 1: Get the Grid Points URL
    points_url = f"{BASE_URL}/points/{lat},{lon}"
    print(f"Requesting Grid Points: {points_url}")
    
    try:
        response = requests.get(points_url, headers=headers, timeout=10)
        response.raise_for_status() # Raise exception for 4xx or 5xx errors
        
        points_data = response.json()
        
        # Extract the hourly forecast URL from the properties object
        hourly_forecast_url = points_data['properties']['forecastHourly']
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching grid points for {lat},{lon}: {e}")
        return []

    # 3. STEP 2: Get the Hourly Forecast Data
    print(f"Requesting Hourly Forecast: {hourly_forecast_url}")

    try:
        response = requests.get(hourly_forecast_url, headers=headers, timeout=10)
        response.raise_for_status() # Raise exception for 4xx or 5xx errors
        
        forecast_data = response.json()
        
        # The forecast periods are nested within 'properties'
        periods = forecast_data['properties']['periods']
        return periods
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching hourly forecast from {hourly_forecast_url}: {e}")
        return []

def format_for_kafka_raw(periods: list, station_id: str) -> list:
    """
    Transforms the raw NWS data into the specific schema required for the
    'weather-raw' Kafka topic for Spark consumption.
    """
    kafka_messages = []
    
    for period in periods:
        # NWS data uses 'startTime' for the hour a forecast begins
        timestamp_str = period.get('startTime')
        
        message = {
            "station_id": station_id,
            "timestamp": timestamp_str,
            "temperature": period.get('temperature'),
            "humidity": period.get('relativeHumidity', {}).get('value'),
            "wind_speed": period.get('windSpeed'),
            "wind_direction": period.get('windDirection'),
            "precipitation_probability": period.get('probabilityOfPrecipitation', {}).get('value'),
            # Note: Pressure is not directly in this forecast endpoint, 
            # you would need the separate '/observations' endpoint for current pressure.
        }
        kafka_messages.append(message)
        
    return kafka_messages

# --- Execution ---
if __name__ == "__main__":
    
    # Define a unique identifier for your station
    STATION_ID = f"NWS_{LATITUDE}_{LONGITUDE}" 
    
    # 1. Fetch the raw hourly data
    raw_periods = fetch_nws_hourly_forecast(LATITUDE, LONGITUDE)
    
    if raw_periods:
        # 2. Format the data for your Kafka Topic
        formatted_messages = format_for_kafka_raw(raw_periods, STATION_ID)

        # 3. Print the first few formatted messages (what you would send to Kafka)
        print("\n--- First 3 Formatted Messages (Ready for Kafka weather-raw) ---")
        for msg in formatted_messages[:3]:
            # In a real producer, you would use a Kafka library here (e.g., confluent-kafka)
            # producer.produce('weather-raw', key=STATION_ID, value=json.dumps(msg))
            print(json.dumps(msg, indent=2))
            
        print(f"\nSuccessfully processed {len(formatted_messages)} hourly forecast periods.")