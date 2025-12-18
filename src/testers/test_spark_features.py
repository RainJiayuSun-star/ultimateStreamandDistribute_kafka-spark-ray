"""
Test consumer for weather-features topic.
Consumes aggregated features produced by Spark streaming to verify Spark is working correctly.

Commands to run:
- In Docker (src/ is mounted to /app/src/)
docker exec -it spark-master python3 /app/src/testers/test_spark_features.py

- Local testing
python3 src/testers/test_spark_features.py
"""

from kafka import KafkaConsumer
import json
import sys
import time
import threading

broker = 'kafka:9092'  # Use 'kafka:9092' in Docker, 'localhost:9092' for local testing
topic_name = 'weather-features'
group_id = 'spark-features-test'

# Choose offset strategy: 'earliest' to see all messages, 'latest' to see only new ones
# Change this if you want to see historical data
OFFSET_STRATEGY = 'earliest'  # Options: 'earliest' or 'latest'

# Initialize Kafka Consumer
# Consumer group for testing Spark output
# Auto-assigns partitions (broker automatically assigns)
consumer = KafkaConsumer(
    bootstrap_servers=[broker], 
    group_id=group_id, 
    auto_offset_reset=OFFSET_STRATEGY,
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None
)

# Subscribe to the weather-features topic
consumer.subscribe([topic_name])

# Wait for assignment to occur
print("Waiting for partition assignment...")
_ = consumer.poll(timeout_ms=5000)

# Show consumer assigned to partitions
assigned_partitions = consumer.assignment()
print(f"Consumer assigned to partitions: {assigned_partitions}")
print(f"Starting to consume aggregated features from topic '{topic_name}'...")
print("=" * 80)
if OFFSET_STRATEGY == 'latest':
    print("⚠️  Using 'latest' offset - will only show NEW messages after this consumer starts.")
    print("   If you want to see historical messages, change OFFSET_STRATEGY to 'earliest' in this script")
    print("   Waiting for new messages from Spark streaming...")
    print("   (Spark processes in batches every ~1 minute, so wait 1-2 minutes for first batch)")
else:
    print("✓ Using 'earliest' offset - will show all historical messages")
    print("  Reading from beginning of topic...")
    print(f"  Assigned to {len(assigned_partitions)} partition(s)")
print("=" * 80)
print("Waiting for messages... (Press Ctrl+C to stop)")
print("=" * 80)

# Quick check: try to peek at first message to see if any exist
if OFFSET_STRATEGY == 'earliest':
    print("\nChecking for existing messages in topic...")
    # Seek to beginning to ensure we can read from start
    for partition in assigned_partitions:
        try:
            consumer.seek(partition, 0)
        except:
            pass
    # Poll once to see if we get any messages immediately
    peek_messages = consumer.poll(timeout_ms=2000)
    if peek_messages:
        print(f"✓ Found {sum(len(msgs) for msgs in peek_messages.values())} message(s) in topic!")
        print("  Starting to display messages...\n")
    else:
        print("⚠️  No messages found in topic yet.")
        print("  This could mean:")
        print("    - Spark streaming hasn't processed any batches yet")
        print("    - Spark streaming is not running")
        print("  Waiting for new messages...\n")
    sys.stdout.flush()
else:
    sys.stdout.flush()

# Consumption Loop
# Loop over messages forever, printing dictionaries corresponding to each message
message_count = 0
start_time = time.time()
last_message_time = time.time()
TIMEOUT_SECONDS = 120  # Warn if no messages for 2 minutes

try:
    for message in consumer:
        last_message_time = time.time()
        
        try:
            # Deserialize the JSON value (already done by value_deserializer)
            features_data = message.value
            
            # Decode the key (already done by key_deserializer)
            # Note: Spark uses station_id as the key, but also includes it in the value
            station_id = message.key if message.key else features_data.get('station_id', 'N/A')
            
            message_count += 1
            
            # Print formatted output
            print(f"\n{'='*80}")
            print(f"Message #{message_count} | Partition {message.partition} | Station: {station_id}")
            print(f"{'='*80}")
            print(f"Window: {features_data.get('window_start', 'N/A')} to {features_data.get('window_end', 'N/A')}")
            print(f"Measurements in window: {features_data.get('measurement_count', 0)}")
            print(f"\nTemperature:")
            print(f"  Mean: {features_data.get('temperature_mean', 'N/A')}°F")
            print(f"  Std:  {features_data.get('temperature_std', 'N/A')}")
            print(f"  Min:  {features_data.get('temperature_min', 'N/A')}°F")
            print(f"  Max:  {features_data.get('temperature_max', 'N/A')}°F")
            print(f"\nHumidity:")
            print(f"  Mean: {features_data.get('humidity_mean', 'N/A')}%")
            print(f"  Std:  {features_data.get('humidity_std', 'N/A')}")
            print(f"  Min:  {features_data.get('humidity_min', 'N/A')}%")
            print(f"  Max:  {features_data.get('humidity_max', 'N/A')}%")
            print(f"\nPressure:")
            print(f"  Mean: {features_data.get('pressure_mean', 'N/A')} hPa")
            print(f"  Std:  {features_data.get('pressure_std', 'N/A')}")
            print(f"  Min:  {features_data.get('pressure_min', 'N/A')} hPa")
            print(f"  Max:  {features_data.get('pressure_max', 'N/A')} hPa")
            print(f"\nWind:")
            print(f"  Speed Mean: {features_data.get('wind_speed_mean', 'N/A')} m/s")
            print(f"  Direction:  {features_data.get('wind_direction_mean', 'N/A')}°")
            print(f"\nPrecipitation:")
            print(f"  Mean: {features_data.get('precipitation_mean', 'N/A')} mm")
            print(f"  Max:  {features_data.get('precipitation_max', 'N/A')} mm")
            print(f"{'-'*80}")
            sys.stdout.flush()
            
            # Show progress every 10 messages
            if message_count % 10 == 0:
                elapsed = time.time() - start_time
                print(f"\n[Progress] Processed {message_count} messages in {elapsed:.1f} seconds ({message_count/elapsed:.1f} msg/sec)\n")
            
        except json.JSONDecodeError as e:
            print(f"\nERROR: Failed to deserialize JSON message: {e}", file=sys.stderr)
            print(f"Raw message value: {message.value}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"\nERROR: Failed to process message: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue
    
except Exception as e:
    # Handle consumer timeout or other errors
    elapsed = time.time() - start_time
    time_since_last = time.time() - last_message_time
    
    if message_count == 0:
        print(f"\n{'='*80}")
        print(f"⚠️  No messages received after {elapsed:.1f} seconds.")
        print(f"{'='*80}\n")
        print("Possible reasons:")
        print("  1. Spark streaming is not running")
        print("  2. Spark hasn't processed any batches yet (wait 1-2 minutes)")
        if OFFSET_STRATEGY == 'latest':
            print("  3. No new messages since consumer started (using 'latest' offset)")
            print("\n💡 TIP: Change OFFSET_STRATEGY to 'earliest' in this script to see historical messages")
        else:
            print("  3. No messages in topic (Spark hasn't produced any yet)")
        print("\nDiagnostic commands:")
        print("  # Check if Spark streaming is running:")
        print("  docker exec spark-master ps aux | grep streaming_app")
        print("\n  # Check Spark logs:")
        print("  docker logs spark-master | tail -30")
        print("\n  # Check topic message count:")
        print("  docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \\")
        print("    kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic weather-features")
        print("\n  # Check if producer is sending data:")
        print("  docker logs kafka | grep 'Published' | tail -5")
    elif time_since_last > TIMEOUT_SECONDS:
        print(f"\n⚠️  No messages received for {time_since_last:.1f} seconds.")
        print(f"   Total messages received so far: {message_count}")
        print("   This might indicate Spark streaming has stopped or there's no new data.")
    else:
        print(f"\nConsumer stopped. Total messages received: {message_count}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
    consumer.close()
    sys.exit(0)

except KeyboardInterrupt:
    elapsed = time.time() - start_time
    print(f"\n\n{'='*80}")
    print(f"Stopped by user.")
    print(f"Total messages received: {message_count}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"{'='*80}")
    consumer.close()

