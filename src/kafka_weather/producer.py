import time
import json
import sys
import requests
from datetime import datetime
from kafka import KafkaAdminClient, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import UnknownTopicOrPartitionError, NoBrokersAvailable

# Configuration
BROKER = 'localhost:9092'  # Use 'kafka:9092' in Docker, 'localhost:9092' for local testing
USER_AGENT = "WeatherForecastingSystem/1.0 (kafka-spark-ray-project, contact@example.com)"
BASE_URL = "https://api.weather.gov"

# Weather stations to monitor (multiple locations)
STATIONS = [
    {"name": "Madison", "lat": 43.0731, "lon": -89.4012},
    {"name": "Milwaukee", "lat": 43.0389, "lon": -87.9065},
    {"name": "Chicago", "lat": 41.8781, "lon": -87.6298},
    {"name": "Minneapolis", "lat": 44.9778, "lon": -93.2650},
    {"name": "Des Moines", "lat": 41.5868, "lon": -93.6250},
]

# Kafka topics to create (3 topics for the pipeline)
TOPICS = [
    {"name": "weather-raw", "partitions": 4, "replication_factor": 1},
    {"name": "weather-features", "partitions": 4, "replication_factor": 1},
    {"name": "weather-predictions", "partitions": 4, "replication_factor": 1},
]

# Fetch interval (seconds) - fetch every 5 minutes -> 15 seconds
FETCH_INTERVAL = 15


def fetch_nws_current_observation(lat: float, lon: float) -> tuple[str, dict]:
    """
    Fetches current weather observation from NWS API.
    Returns (station_id, observation_data).
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json'
    }
    
    # Step 1: Find nearest station
    stations_url = f"{BASE_URL}/points/{lat},{lon}/stations"
    station_id = f"UNKNOWN_{lat}_{lon}"
    
    try:
        response = requests.get(stations_url, headers=headers, timeout=10)
        response.raise_for_status()
        stations_data = response.json()
        
        if stations_data.get('features'):
            station_id = stations_data['features'][0]['properties']['stationIdentifier']
            print(f"  Found station: {station_id}")
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching station list: {e}")
        return station_id, {}
    
    # Step 2: Get latest observation
    latest_obs_url = f"{BASE_URL}/stations/{station_id}/observations/latest"
    
    try:
        response = requests.get(latest_obs_url, headers=headers, timeout=10)
        response.raise_for_status()
        return station_id, response.json().get('properties', {})
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching observation for {station_id}: {e}")
        return station_id, {}


def format_weather_data(station_id: str, station_name: str, raw_obs: dict) -> dict:
    """
    Formats raw NWS observation data for Kafka weather-raw topic.
    """
    if not raw_obs:
        return {}
    
    # Temperature: Keep in Celsius (metric) - model was trained on Celsius
    # DO NOT convert to Fahrenheit - the LSTM model expects Celsius
    temp_c = raw_obs.get('temperature', {}).get('value')
    # Store as temperature (Celsius) - model expects metric units
    temperature = round(temp_c, 1) if temp_c is not None else None
    
    # Pressure: Pascals to hectopascals
    pressure_pa = raw_obs.get('barometricPressure', {}).get('value')
    pressure_hpa = round(pressure_pa / 100, 2) if pressure_pa is not None else None
    
    # Precipitation
    precip_m = raw_obs.get('precipitationLastHour', {}).get('value')
    precipitation = round(precip_m, 3) if precip_m is not None else 0.0
    
    # Other fields
    wind_speed = raw_obs.get('windSpeed', {}).get('value')
    humidity = raw_obs.get('relativeHumidity', {}).get('value')
    wind_direction = raw_obs.get('windDirection', {}).get('value')
    
    return {
        "station_id": station_id,
        "station_name": station_name,
        "timestamp": raw_obs.get('timestamp', datetime.utcnow().isoformat()),
        "temperature": temperature,  # Celsius (metric) - matches model training
        "humidity": round(humidity, 2) if humidity is not None else None,
        "wind_speed": wind_speed,  # m/s (metric) - matches model training
        "wind_direction": wind_direction,
        "sea_level_pressure": pressure_hpa,
        "precipitation_last_hour": precipitation,
    }


def create_kafka_topics(admin_client: KafkaAdminClient):
    """
    Creates Kafka topics. Deletes existing topics first if they exist.
    Based on p7 structure: delete first, then create.
    """
    topic_names = [topic["name"] for topic in TOPICS]
    
    # Delete existing topics
    try:
        admin_client.delete_topics(topic_names)
        print(f"Deleted existing topics: {topic_names}")
    except UnknownTopicOrPartitionError:
        print("Topics don't exist yet (this is OK)")
    
    # Wait for deletion to complete (p7 uses 3 seconds)
    time.sleep(3)
    
    # Create topics
    new_topics = [
        NewTopic(
            name=topic["name"],
            num_partitions=topic["partitions"],
            replication_factor=topic["replication_factor"]
        )
        for topic in TOPICS
    ]
    
    admin_client.create_topics(new_topics)
    print(f"Created topics: {[t.name for t in new_topics]}")
    
    # List all topics
    existing_topics = admin_client.list_topics()
    print(f"Existing topics: {list(existing_topics)}")


def main():
    """
    Main producer loop: creates topics, then continuously fetches and publishes weather data.
    """
    print("=" * 60)
    print("Weather Data Producer Starting...")
    print("=" * 60)
    
    # Initialize Kafka admin client with retry logic
    print("\n[1/3] Initializing Kafka admin client...")
    admin_client = None
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=[BROKER])
            # Test connection by listing topics
            admin_client.list_topics()
            print("  ✓ Successfully connected to Kafka broker")
            break
        except NoBrokersAvailable:
            retry_count += 1
            if retry_count < max_retries:
                print(f"  ⏳ Kafka broker not ready yet, retrying ({retry_count}/{max_retries})...")
                time.sleep(2)
            else:
                print(f"  ✗ ERROR: Could not connect to Kafka broker after {max_retries} attempts")
                print(f"     Make sure Kafka is running on {BROKER}")
                sys.exit(1)
        except Exception as e:
            print(f"  ✗ ERROR: Unexpected error connecting to Kafka: {e}")
            sys.exit(1)
    
    # Create Kafka topics
    print("\n[2/3] Creating Kafka topics...")
    create_kafka_topics(admin_client)
    
    # Initialize Kafka producer
    # Requirements from p7:
    # 1. retries up to 10 times when send requests fail
    # 2. send calls are not acknowledged until all in-sync replicas have received the data
    # Note: KafkaProducer is lazy - it only connects when first used
    print("\n[3/3] Initializing Kafka producer...")
    producer = KafkaProducer(
        bootstrap_servers=[BROKER],
        retries=10,
        acks='all',  # Wait for all in-sync replicas
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )
    print("  ✓ Kafka producer initialized successfully")
    
    # Main loop: continuously fetch and publish weather data
    print(f"\n{'=' * 60}")
    print(f"Starting weather data production loop (every {FETCH_INTERVAL} seconds)")
    print(f"Monitoring {len(STATIONS)} stations")
    print(f"{'=' * 60}\n")
    
    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"\n--- Iteration {iteration} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            
            messages_sent = 0
            for station in STATIONS:
                station_name = station["name"]
                lat = station["lat"]
                lon = station["lon"]
                
                print(f"\nFetching data for {station_name} ({lat}, {lon})...")
                
                # Fetch weather data
                station_id, raw_observation = fetch_nws_current_observation(lat, lon)
                
                if raw_observation:
                    # Format data for Kafka
                    formatted_message = format_weather_data(station_id, station_name, raw_observation)
                    
                    if formatted_message:
                        # Publish to Kafka
                        # Requirement from p7: use station ID as the message's key
                        msg_key = station_id
                        msg_value = formatted_message
                        
                        # Send to weather-raw topic
                        future = producer.send(
                            "weather-raw",
                            key=msg_key,
                            value=msg_value
                        )
                        
                        # Optional: wait for send to complete (for debugging)
                        # future.get(timeout=10)
                        
                        messages_sent += 1
                        print(f"  ✓ Published to weather-raw (key: {station_id})")
                    else:
                        print(f"  ✗ Failed to format data for {station_id}")
                else:
                    print(f"  ✗ No observation data retrieved for {station_name}")
            
            print(f"\n✓ Iteration {iteration} complete: {messages_sent}/{len(STATIONS)} messages sent")
            print(f"Waiting {FETCH_INTERVAL} seconds until next fetch...")
            
            # Wait before next iteration
            time.sleep(FETCH_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nShutting down producer...")
    except Exception as e:
        print(f"\n\nError in producer loop: {e}")
        raise
    finally:
        # Flush and close producer
        producer.flush()
        producer.close()
        print("Producer closed.")


if __name__ == "__main__":
    main()
