"""
Debug Consumer for weather-raw topic
Similar to p7 debug consumer, but adapted for JSON messages instead of protobuf.

Commands to run:
- In Docker (src/ is mounted to /app/src/)
docker exec -it kafka python3 /app/src/testers/debug_consumer.py

- Local testing
python3 src/testers/debug_consumer.py
"""

from kafka import KafkaConsumer
import json
import sys

broker = 'localhost:9092'  # Use 'kafka:9092' in Docker, 'localhost:9092' for local testing
topic_name = 'weather-raw'
group_id = 'debug'

# Initialize Kafka Consumer
# Consumer group named "debug"
# Auto-assigns partitions (broker automatically assigns)
# Does NOT seek to beginning (auto_offset_reset='latest')
consumer = KafkaConsumer(
    bootstrap_servers=[broker], 
    group_id=group_id, 
    auto_offset_reset='latest',  # Start from latest messages, not beginning
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None
)

# Subscribe to the weather-raw topic
consumer.subscribe([topic_name])

# Wait for assignment to occur (recommended pause)
print("Waiting for partition assignment...")
# We must poll once to initiate the group membership and assignment process
_ = consumer.poll(timeout_ms=5000)

# Show consumer assigned to partitions
print(f"Consumer assigned to partitions: {consumer.assignment()}")
print(f"Starting to consume messages from topic '{topic_name}'...")
print("=" * 80)
sys.stdout.flush()

# Consumption Loop
# Loop over messages forever, printing dictionaries corresponding to each message
for message in consumer:
    try:
        # Deserialize the JSON value (already done by value_deserializer)
        weather_data = message.value
        
        # Decode the key (already done by key_deserializer)
        station_id = message.key if message.key else "N/A"
        
        # Create the dictionary output format
        # Include partition number like in p7 example
        output_dict = {
            'station_id': station_id,
            'station_name': weather_data.get('station_name', 'N/A'),
            'timestamp': weather_data.get('timestamp', 'N/A'),
            'temperature': weather_data.get('temperature'),
            'humidity': weather_data.get('humidity'),
            'wind_speed': weather_data.get('wind_speed'),
            'wind_direction': weather_data.get('wind_direction'),
            'sea_level_pressure': weather_data.get('sea_level_pressure'),
            'precipitation_last_hour': weather_data.get('precipitation_last_hour'),
            'partition': message.partition  # Extract the partition from the ConsumerRecord
        }
        
        # Print the dictionary
        print(output_dict)
        sys.stdout.flush()
        
    except json.JSONDecodeError as e:
        print(f"Error deserializing JSON message: {e}")
        print(f"Raw message value: {message.value}")
        continue
    except Exception as e:
        print(f"Error processing message: {e}")
        continue

