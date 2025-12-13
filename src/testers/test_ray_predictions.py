"""
Test consumer for weather-predictions topic.
Consumes predictions produced by Ray ML inference to verify the ML pipeline is working.

Commands to run:
- In Docker (src/ is mounted to /app/src/)
docker exec -it ray-head python3 /app/src/testers/test_ray_predictions.py

- Local testing
python3 src/testers/test_ray_predictions.py
"""

from kafka import KafkaConsumer
import json
import sys

# Configuration
# Use 'kafka:9092' in Docker, 'localhost:9092' for local testing
broker = 'kafka:9092' 
topic_name = 'weather-predictions'
group_id = 'ray-predictions-test-group'

# Initialize Kafka Consumer
consumer = KafkaConsumer(
    bootstrap_servers=[broker], 
    group_id=group_id, 
    auto_offset_reset='latest',  # Start from latest messages
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None
)

# Subscribe to the weather-predictions topic
consumer.subscribe([topic_name])

print("Waiting for partition assignment for 'weather-predictions' topic...")
_ = consumer.poll(timeout_ms=5000)

print(f"Consumer assigned to partitions: {consumer.assignment()}")
print(f"Starting to consume predictions from topic '{topic_name}'...")
print("=" * 80)
sys.stdout.flush()

# Consumption Loop
message_count = 0
try:
    for message in consumer:
        try:
            prediction_data = message.value
            station_id = message.key if message.key else "N/A"
            
            message_count += 1
            
            # Print formatted output
            print(f"\n--- Prediction #{message_count} ---")
            print(f"Station ID: {station_id}")
            print(f"Partition: {message.partition}")
            print(f"Timestamp: {prediction_data.get('timestamp', 'N/A')}")
            print(f"Window: {prediction_data.get('window_start', 'N/A')} to {prediction_data.get('window_end', 'N/A')}")
            
            # Forecast information
            forecast = prediction_data.get('forecast', {})
            if forecast:
                predictions = forecast.get('temperature_predictions', [])
                print(f"\nTemperature Forecast (next {forecast.get('horizon_hours', 24)} hours):")
                if predictions:
                    print(f"  First 6 hours: {[round(p, 1) for p in predictions[:6]]}")
                    print(f"  Average: {round(sum(predictions) / len(predictions), 1)}°F")
            
            # Anomaly information
            anomaly = prediction_data.get('anomaly', {})
            if anomaly:
                is_anomaly = anomaly.get('is_anomaly', False)
                score = anomaly.get('score', 0.0)
                reasons = anomaly.get('reasons', [])
                print(f"\nAnomaly Detection:")
                print(f"  Is Anomaly: {is_anomaly}")
                print(f"  Score: {score:.3f}")
                print(f"  Reasons: {', '.join(reasons)}")
            
            # Current conditions
            current = prediction_data.get('current_conditions', {})
            if current:
                print(f"\nCurrent Conditions:")
                print(f"  Temperature: {current.get('temperature_mean', 'N/A')}°F")
                print(f"  Humidity: {current.get('humidity_mean', 'N/A')}%")
                print(f"  Pressure: {current.get('pressure_mean', 'N/A')} hPa")
                print(f"  Wind Speed: {current.get('wind_speed_mean', 'N/A')} m/s")
            
            print("-" * 80)
            sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            print(f"Error deserializing JSON message: {e}", file=sys.stderr)
            print(f"Raw message value: {message.value}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error processing message: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue

except KeyboardInterrupt:
    print(f"\n\nStopped. Total predictions received: {message_count}")
    consumer.close()

