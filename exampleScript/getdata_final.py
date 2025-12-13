import requests
import json
from datetime import datetime
import socket

# --- Configuration ---
# 1. Location for your "station" (Madison, WI)
LATITUDE = 43.0731
LONGITUDE = -89.4012

# 2. Required User-Agent Header (NWS API requirement for identification)
# **Crucial:** Replace with your actual project details and contact email
USER_AGENT = "MyKafkaRayWeatherProject/1.0 (personal-project.com, contact@example.com)" 
BASE_URL = "https://api.weather.gov"

# --- Functions ---

def fetch_nws_current_observation(lat: float, lon: float) -> tuple[str, dict]:
    """
    **REVISED:** Performs the two-step API call.
    Returns the station ID (str) retrieved from Step 1, and the raw observation properties (dict) from Step 2.
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json' 
    }
    
    # --- STEP 1: Find the nearest observation stations to get the Station ID ---
    stations_url = f"{BASE_URL}/points/{lat},{lon}/stations"
    print(f"Finding nearby stations: {stations_url}")
    
    # Initialize station_id with a fallback based on coordinates
    station_id = f"UNKNOWN_{lat}_{lon}"
    
    try:
        response = requests.get(stations_url, headers=headers, timeout=10)
        response.raise_for_status() 
        stations_data = response.json()
        
        if stations_data['features']:
            # Successfully retrieved the official station ID (e.g., KMSN)
            station_id = stations_data['features'][0]['properties']['stationIdentifier']
            print(f"Found nearest station: {station_id}")
        else:
            print("Error: No nearby weather stations found.")
            # Use fallback ID from initialization
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching station list: {e}")
        return station_id, {}

    # --- STEP 2: Get the latest observation using the retrieved Station ID ---
    latest_obs_url = f"{BASE_URL}/stations/{station_id}/observations/latest"
    print(f"Requesting latest observation: {latest_obs_url}")

    try:
        response = requests.get(latest_obs_url, headers=headers, timeout=10)
        response.raise_for_status() 
        # Return the valid station_id and the observation properties
        return station_id, response.json().get('properties', {})
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest observation: {e}")
        return station_id, {}


def format_current_data_for_kafka(station_id: str, raw_obs: dict) -> dict:
    """
    **REVISED:** Takes the confirmed station_id as a separate argument for accuracy.
    Transforms raw NWS observation data into the 'weather-raw' Kafka schema,
    performing conversions and handling null/missing values.
    """
    if not raw_obs:
        return {}
    
    # Temperature conversion: Celsius to Fahrenheit (F)
    temp_c = raw_obs.get('temperature', {}).get('value')
    temp_f = round((temp_c * 9/5) + 32, 1) if temp_c is not None else None
    
    # Pressure: Using 'barometricPressure' (Altimeter) as proxy for sea-level pressure.
    # Pascals (Pa) to hectopascals (hPa/mbar)
    pressure_pa = raw_obs.get('barometricPressure', {}).get('value')
    pressure_hpa = round(pressure_pa / 100, 2) if pressure_pa is not None else None
    
    # Precipitation: Default to 0.0 if null/missing
    precip_m = raw_obs.get('precipitationLastHour', {}).get('value')
    precipitation_value = round(precip_m, 3) if precip_m is not None else 0.0

    # Extract other fields
    wind_m_s = raw_obs.get('windSpeed', {}).get('value')
    humidity = raw_obs.get('relativeHumidity', {}).get('value')

    return {
        "station_id": station_id, # CORRECTED: Using the explicitly passed ID
        "timestamp": raw_obs.get('timestamp'), 
        "temperature": temp_f,
        "humidity": round(humidity, 2) if humidity is not None else None,
        "wind_speed": wind_m_s,
        "wind_direction": raw_obs.get('windDirection', {}).get('value'),
        "sea_level_pressure": pressure_hpa,
        "precipitation_last_hour": precipitation_value,
    }

def produce_to_kafka(topic: str, station_id: str, message: dict):
    """
    Placeholder function for producing the message to Kafka.
    Requires 'confluent-kafka' to be installed.
    """
    try:
        from confluent_kafka import Producer
    except ImportError:
        print("\n*** KAFKA LIBRARY NOT FOUND ***")
        print("Install 'confluent-kafka' to enable this feature (pip install confluent-kafka)")
        print(f"Simulating Kafka production: Produced message for topic '{topic}' with key '{station_id}'.")
        return

    # Use 'kafka' as the hostname in Docker Compose
    conf = {'bootstrap.servers': 'kafka:9092', 
            'client.id': socket.gethostname()}
    
    producer = Producer(conf)

    # Key is essential for parallel processing and ordering in your design!
    key = station_id.encode('utf-8') 
    value = json.dumps(message).encode('utf-8')
    
    producer.produce(topic, key=key, value=value)
    
    producer.flush()
    print(f"\nSuccessfully produced 1 message to Kafka topic '{topic}' with key '{station_id}'.")

# --- Execution ---

if __name__ == "__main__":
    
    KAFKA_TOPIC = "weather-raw"
    
    # 1. Fetch both the station ID and the raw observation data
    # The return is now guaranteed to separate the ID from the data.
    station_id, raw_observation = fetch_nws_current_observation(LATITUDE, LONGITUDE)
    
    if raw_observation:
        # 2. Pass the explicitly retrieved station_id to the formatting function
        formatted_message = format_current_data_for_kafka(station_id, raw_observation)

        print("\n--- Formatted Current Observation Message (Ready for Kafka weather-raw) ---")
        print(json.dumps(formatted_message, indent=2))

        # 3. Produce to Kafka
        # Note: This will only work if Kafka and the confluent-kafka library are properly set up.
        produce_to_kafka(KAFKA_TOPIC, station_id, formatted_message)
        
    else:
        print(f"Could not retrieve current observation data for station ID: {station_id}. Check API connection.")