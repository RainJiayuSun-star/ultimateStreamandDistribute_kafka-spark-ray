import requests
import json
from datetime import datetime, timezone

# --- Configuration (Same as before) ---
LATITUDE = 43.0731  # Example: Madison, WI
LONGITUDE = -89.4012
USER_AGENT = "MyKafkaRayWeatherProject/1.0 (personal-project.com, contact@example.com)" 
BASE_URL = "https://api.weather.gov"

# --- Function to Get Current Data ---

def fetch_nws_current_observation(lat: float, lon: float) -> dict:
    """
    Fetches the latest observation from the nearest NWS weather station.
    Returns the raw observation properties.
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json' 
    }
    
    # 1. STEP 1: Find the nearest observation stations
    stations_url = f"{BASE_URL}/points/{lat},{lon}/stations"
    # ... (Step 1 is unchanged, assumes success based on your output) ...
    try:
        response = requests.get(stations_url, headers=headers, timeout=10)
        response.raise_for_status() 
        stations_data = response.json()
        if not stations_data['features']:
            print("Error: No nearby weather stations found.")
            return {}
        station_id = stations_data['features'][0]['properties']['stationIdentifier']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching station list: {e}")
        return {}

    # 2. STEP 2: Get the latest observation from that station
    latest_obs_url = f"{BASE_URL}/stations/{station_id}/observations/latest"
    print(f"Requesting latest observation: {latest_obs_url}")

    try:
        response = requests.get(latest_obs_url, headers=headers, timeout=10)
        response.raise_for_status() 
        return response.json().get('properties', {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest observation: {e}")
        return {}


def format_current_data_for_kafka(raw_obs: dict, lat: float, lon: float) -> dict:
    """
    Transforms raw NWS observation data into the 'weather-raw' Kafka schema,
    handling common null/missing values for robust feature creation.
    """
    if not raw_obs:
        return {}

    # 1. FIX: Ensure station_id is correctly pulled or generated as a fallback
    station_id = raw_obs.get('stationIdentifier', f"UNKNOWN_{lat}_{lon}")
    
    # 2. Temperature (C -> F)
    temp_c = raw_obs.get('temperature', {}).get('value')
    temp_f = round((temp_c * 9/5) + 32, 1) if temp_c is not None else None
    
    # 3. FIX: Use 'barometricPressure' (Altimeter) if 'seaLevelPressure' is null/missing
    # Pressure is in Pascals (Pa). Convert to hectopascals (hPa/mbar).
    pressure_pa = raw_obs.get('barometricPressure', {}).get('value')
    pressure_hpa = round(pressure_pa / 100, 2) if pressure_pa is not None else None
    
    # 4. FIX: Default Precipitation to 0.0 if null/missing
    # Precipitation is in meters (m) over the last hour.
    precip_m = raw_obs.get('precipitationLastHour', {}).get('value')
    precipitation_value = round(precip_m, 3) if precip_m is not None else 0.0 # Default to 0.0

    # 5. Extract other fields
    wind_m_s = raw_obs.get('windSpeed', {}).get('value')
    humidity = raw_obs.get('relativeHumidity', {}).get('value')

    return {
        "station_id": station_id,
        "timestamp": raw_obs.get('timestamp'), # ISO-8601 string
        "temperature": temp_f, # F
        "humidity": round(humidity, 2) if humidity is not None else None, # %
        "wind_speed": wind_m_s, # m/s
        "wind_direction": raw_obs.get('windDirection', {}).get('value'), # degrees
        "sea_level_pressure": pressure_hpa, # hPa/mbar (Now using Altimeter)
        "precipitation_last_hour": precipitation_value, # Defaulted to 0.0 if not reported
    }

# --- Execution ---
if __name__ == "__main__":
    
    raw_observation = fetch_nws_current_observation(LATITUDE, LONGITUDE)
    
    if raw_observation:
        # Pass LAT and LON to the formatting function for the UNKNOWN station fallback
        formatted_message = format_current_data_for_kafka(raw_observation, LATITUDE, LONGITUDE)

        print("\n--- Formatted Current Observation Message (Ready for Kafka weather-raw) ---")
        print(json.dumps(formatted_message, indent=2))
        
    else:
        print("Could not retrieve current observation data.")