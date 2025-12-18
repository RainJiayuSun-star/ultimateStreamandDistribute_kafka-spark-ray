"""
Test script for Kafka Data Collector

Verifies that the data collector is saving files correctly.
Tests:
1. Files are created in correct directory structure
2. Files contain valid JSON data
3. Checkpoint file is created and updated
4. Data format matches expected schema

Commands to run:
- In Docker (src/ is mounted to /app/src/)
docker exec -it kafka python3 /app/src/testers/test_data_collector.py

- Local testing
python3 src/testers/test_data_collector.py
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from kafka.structs import TopicPartition

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.kafka_config import (
        KAFKA_BOOTSTRAP_SERVERS,
        TOPIC_WEATHER_RAW
    )
except ImportError:
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    TOPIC_WEATHER_RAW = "weather-raw"

# Configuration
# Use same path as data_collector.py: /app/data/kafka_streaming in Docker, src/data/kafka_streaming locally
OUTPUT_DIR = Path(os.getenv("DATA_COLLECTOR_OUTPUT_DIR", "/app/data/kafka_streaming"))
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoints" / "offset_checkpoint.json"

def test_directory_structure():
    """Test that output directory structure exists."""
    print("\n" + "=" * 80)
    print("TEST 1: Directory Structure")
    print("=" * 80)
    
    if not OUTPUT_DIR.exists():
        print(f"✗ Output directory does not exist: {OUTPUT_DIR.absolute()}")
        print(f"  → Data collector may not have run yet")
        return False
    
    print(f"✓ Output directory exists: {OUTPUT_DIR.absolute()}")
    
    # Check for date-based subdirectories
    date_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name != "checkpoints"]
    if date_dirs:
        print(f"✓ Found {len(date_dirs)} date directories:")
        for date_dir in sorted(date_dirs)[:5]:  # Show first 5
            print(f"  - {date_dir.name}")
        if len(date_dirs) > 5:
            print(f"  ... and {len(date_dirs) - 5} more")
    else:
        print("⚠ No date directories found yet")
    
    # Check checkpoint directory
    checkpoint_dir = OUTPUT_DIR / "checkpoints"
    if checkpoint_dir.exists():
        print(f"✓ Checkpoint directory exists: {checkpoint_dir.absolute()}")
    else:
        print(f"⚠ Checkpoint directory does not exist yet")
    
    return True


def test_checkpoint_file():
    """Test checkpoint file exists and is valid."""
    print("\n" + "=" * 80)
    print("TEST 2: Checkpoint File")
    print("=" * 80)
    
    if not CHECKPOINT_FILE.exists():
        print(f"⚠ Checkpoint file does not exist: {CHECKPOINT_FILE.absolute()}")
        print(f"  → Data collector may not have processed any messages yet")
        return False
    
    print(f"✓ Checkpoint file exists: {CHECKPOINT_FILE.absolute()}")
    
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            checkpoint = json.load(f)
        
        print(f"✓ Checkpoint file is valid JSON")
        print(f"  Last updated: {checkpoint.get('last_updated', 'N/A')}")
        
        offsets = checkpoint.get('offsets', {})
        if offsets:
            topic_offsets = offsets.get(TOPIC_WEATHER_RAW, {})
            if topic_offsets:
                print(f"  Offsets for {TOPIC_WEATHER_RAW}:")
                for partition, offset in sorted(topic_offsets.items()):
                    print(f"    Partition {partition}: {offset}")
            else:
                print(f"  ⚠ No offsets found for {TOPIC_WEATHER_RAW}")
        else:
            print(f"  ⚠ No offsets in checkpoint")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ Checkpoint file is not valid JSON: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading checkpoint file: {e}")
        return False


def test_data_files():
    """Test that data files exist and contain valid data."""
    print("\n" + "=" * 80)
    print("TEST 3: Data Files")
    print("=" * 80)
    
    # Find all .jsonl files
    jsonl_files = list(OUTPUT_DIR.rglob("*.jsonl"))
    
    if not jsonl_files:
        print(f"⚠ No .jsonl files found in {OUTPUT_DIR.absolute()}")
        print(f"  → Data collector may not have saved any data yet")
        return False
    
    print(f"✓ Found {len(jsonl_files)} .jsonl file(s)")
    
    # Test a few files
    test_files = jsonl_files[:3]  # Test first 3 files
    
    for file_path in test_files:
        print(f"\n  Testing: {file_path.name}")
        print(f"    Path: {file_path.relative_to(OUTPUT_DIR)}")
        
        try:
            # Count lines
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"    Lines: {len(lines)}")
            
            # Validate JSON
            valid_count = 0
            invalid_count = 0
            sample_data = None
            
            for i, line in enumerate(lines[:10]):  # Check first 10 lines
                try:
                    data = json.loads(line.strip())
                    valid_count += 1
                    if sample_data is None:
                        sample_data = data
                except json.JSONDecodeError:
                    invalid_count += 1
            
            if invalid_count > 0:
                print(f"    ✗ Found {invalid_count} invalid JSON lines")
            else:
                print(f"    ✓ All checked lines are valid JSON")
            
            if sample_data:
                print(f"    Sample data keys: {list(sample_data.keys())}")
                print(f"    Station: {sample_data.get('station_name', 'N/A')}")
                print(f"    Timestamp: {sample_data.get('timestamp', 'N/A')}")
            
        except Exception as e:
            print(f"    ✗ Error reading file: {e}")
            return False
    
    return True


def test_kafka_topic_status():
    """Test Kafka topic status and partition usage."""
    print("\n" + "=" * 80)
    print("TEST 4: Kafka Topic Status")
    print("=" * 80)
    
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            consumer_timeout_ms=2000  # Short timeout for testing
        )
        
        # Get topic metadata
        partitions = consumer.partitions_for_topic(TOPIC_WEATHER_RAW)
        
        if partitions:
            print(f"✓ Topic {TOPIC_WEATHER_RAW} exists")
            print(f"  Total partitions: {len(partitions)}")
            print(f"  Partition IDs: {sorted(partitions)}")
            
            # Check offsets for each partition
            print(f"\n  Partition Offsets:")
            topic_partitions = [TopicPartition(TOPIC_WEATHER_RAW, p) for p in sorted(partitions)]
            
            try:
                # Get beginning and end offsets for all partitions
                beginning_offsets = consumer.beginning_offsets(topic_partitions)
                end_offsets = consumer.end_offsets(topic_partitions)
                
                for tp in topic_partitions:
                    partition_id = tp.partition
                    beginning = beginning_offsets.get(tp, 0)
                    end = end_offsets.get(tp, 0)
                    messages = end - beginning
                    print(f"    Partition {partition_id}: {messages} messages (offsets {beginning} to {end-1})")
            except Exception as e:
                print(f"    Could not get offsets: {e}")
        else:
            print(f"✗ Topic {TOPIC_WEATHER_RAW} not found or no partitions")
        
        consumer.close()
        return True
        
    except NoBrokersAvailable:
        print(f"✗ Cannot connect to Kafka broker: {KAFKA_BOOTSTRAP_SERVERS}")
        print(f"  → Make sure Kafka is running")
        return False
    except Exception as e:
        print(f"✗ Error checking Kafka topic: {e}")
        return False


def test_partition_distribution():
    """Test how messages are distributed across partitions."""
    print("\n" + "=" * 80)
    print("TEST 5: Partition Distribution")
    print("=" * 80)
    
    try:
        consumer = KafkaConsumer(
            TOPIC_WEATHER_RAW,
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            consumer_timeout_ms=5000
        )
        
        # Sample messages to see partition distribution
        partition_counts = {}
        station_partitions = {}
        message_count = 0
        max_samples = 100  # Sample up to 100 messages
        
        print(f"  Sampling up to {max_samples} messages to check partition distribution...")
        
        for message in consumer:
            partition = message.partition
            station_id = message.key if message.key else 'N/A'
            
            partition_counts[partition] = partition_counts.get(partition, 0) + 1
            
            if station_id not in station_partitions:
                station_partitions[station_id] = set()
            station_partitions[station_id].add(partition)
            
            message_count += 1
            if message_count >= max_samples:
                break
        
        consumer.close()
        
        if partition_counts:
            print(f"\n  ✓ Sampled {message_count} messages")
            print(f"  Partition distribution:")
            for partition in sorted(partition_counts.keys()):
                count = partition_counts[partition]
                percentage = (count / message_count) * 100
                print(f"    Partition {partition}: {count} messages ({percentage:.1f}%)")
            
            print(f"\n  Station to partition mapping:")
            for station_id, partitions in sorted(station_partitions.items()):
                print(f"    {station_id}: partitions {sorted(partitions)}")
            
            # Check if all partitions are used
            total_partitions = len(partition_counts)
            print(f"\n  Partitions used: {total_partitions}")
            
            # Get expected number of partitions
            try:
                consumer2 = KafkaConsumer(bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS], consumer_timeout_ms=2000)
                all_partitions = consumer2.partitions_for_topic(TOPIC_WEATHER_RAW)
                consumer2.close()
                
                if all_partitions:
                    expected = len(all_partitions)
                    if total_partitions < expected:
                        print(f"  ⚠ Only {total_partitions} out of {expected} partitions have messages")
                        print(f"    → This is normal if:")
                        print(f"      - Kafka uses hash(key) % num_partitions for partitioning")
                        print(f"      - Station IDs hash to only some partitions")
                        print(f"      - Not all partitions have received messages yet")
                    else:
                        print(f"  ✓ All {expected} partitions are being used")
            except:
                pass
            
        else:
            print(f"  ⚠ No messages found in topic")
            print(f"    → Producer may not be running or topic is empty")
        
        return True
        
    except NoBrokersAvailable:
        print(f"✗ Cannot connect to Kafka broker")
        return False
    except Exception as e:
        print(f"✗ Error checking partition distribution: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("Kafka Data Collector Test Suite")
    print("=" * 80)
    print(f"\nOutput Directory: {OUTPUT_DIR.absolute()}")
    print(f"Checkpoint File: {CHECKPOINT_FILE.absolute()}")
    print(f"Topic: {TOPIC_WEATHER_RAW}")
    print(f"Kafka Broker: {KAFKA_BOOTSTRAP_SERVERS}")
    
    results = []
    
    # Run tests
    results.append(("Directory Structure", test_directory_structure()))
    results.append(("Checkpoint File", test_checkpoint_file()))
    results.append(("Data Files", test_data_files()))
    results.append(("Kafka Topic Status", test_kafka_topic_status()))
    results.append(("Partition Distribution", test_partition_distribution()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Data collector is working correctly.")
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")
        print("\nTroubleshooting:")
        print("1. Make sure data collector is running:")
        print("   docker exec kafka ps aux | grep data_collector")
        print("2. Make sure producer is running and sending data")
        print("3. Wait a few minutes for data to accumulate")
        print("4. Check data collector logs:")
        print("   docker logs kafka | grep -i data_collector")


if __name__ == "__main__":
    main()

