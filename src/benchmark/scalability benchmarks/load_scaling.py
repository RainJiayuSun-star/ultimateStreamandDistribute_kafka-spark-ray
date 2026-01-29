"""
Load scaling benchmarks.

Tests performance with different message rates (load levels).
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from kafka import KafkaProducer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import UnknownTopicOrPartitionError

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from metrics_collector import MetricsCollector

# Import generate_synthetic_weather_data from scripts
scripts_path = os.path.join(os.path.dirname(__file__), '../../scripts')
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

try:
    from benchmark_partition_scaling import generate_synthetic_weather_data
except ImportError:
    # Fallback: define function locally if import fails
    import random
    from datetime import datetime
    def generate_synthetic_weather_data(station_id: str, station_name: str, base_temp: float = None) -> dict:
        """Generate synthetic weather data."""
        if base_temp is None:
            base_temp = random.uniform(15.0, 25.0)
        temperature = round(base_temp + random.uniform(-2.0, 2.0), 1)
        humidity = round(random.uniform(40.0, 90.0), 2)
        wind_speed = round(random.uniform(0.0, 15.0), 2)
        wind_direction = random.randint(0, 360)
        sea_level_pressure = round(random.uniform(980.0, 1020.0), 2)
        precipitation = round(random.uniform(0.0, 5.0), 3)
        return {
            "station_id": station_id,
            "station_name": station_name,
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "sea_level_pressure": sea_level_pressure,
            "precipitation_last_hour": precipitation,
        }


def run_load_scaling_tests(
    rates_list: List[float],
    stations: int = 50,
    duration: int = 300,
    broker: str = None,
    results_dir: Path = None
) -> Dict:
    """
    Run load scaling tests with different message rates.
    """
    if results_dir is None:
        # Check if running inside Docker
        is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
        if is_inside_docker:
            # Use writable location
            results_dir = Path('/tmp') / 'benchmark_results'
        else:
            results_dir = Path(__file__).parent / 'output'
    
    results_dir.mkdir(parents=True, exist_ok=True)
    
    broker = broker or os.getenv('KAFKA_BROKER', 'localhost:9092')
    collector = MetricsCollector(broker=broker)
    
    # Create benchmark topic
    topic_name = 'weather-raw-load-test'
    admin_client = KafkaAdminClient(bootstrap_servers=[broker])
    
    try:
        admin_client.delete_topics([topic_name])
        time.sleep(3)
    except UnknownTopicOrPartitionError:
        pass
    
    new_topic = NewTopic(name=topic_name, num_partitions=4, replication_factor=1)
    admin_client.create_topics([new_topic])
    print(f"Created topic: {topic_name}")
    
    results = {
        'test_type': 'load_scaling',
        'rates_tested': rates_list,
        'stations': stations,
        'duration_per_test': duration,
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    producer = KafkaProducer(
        bootstrap_servers=[broker],
        retries=10,
        acks='all',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )
    
    try:
        for rate in rates_list:
            print(f"\n{'=' * 80}")
            print(f"Testing load: {rate} msg/sec")
            print(f"{'=' * 80}")
            
            # Wait for system to stabilize
            print("Waiting for system to stabilize...")
            time.sleep(5)
            
            # Collect baseline metrics
            print("Collecting baseline metrics...")
            baseline_metrics = collector.collect_all_metrics(duration=5.0)
            
            # Generate station IDs
            station_ids = [f"LOAD_{i:03d}" for i in range(stations)]
            
            # Calculate interval between messages
            interval = 1.0 / rate if rate > 0 else 1.0
            
            # Start metrics collection in parallel
            print(f"Generating load at {rate} msg/sec for {duration} seconds...")
            
            test_metrics = []
            messages_sent = 0
            errors = 0
            start_time = time.time()
            last_metrics_time = start_time
            
            while time.time() - start_time < duration:
                message_start = time.time()
                
                # Select random station
                station_id = station_ids[messages_sent % len(station_ids)]
                station_name = f"LoadTest-Station-{station_id}"
                
                # Generate synthetic data
                message = generate_synthetic_weather_data(station_id, station_name)
                
                # Send message
                try:
                    future = producer.send(topic_name, key=station_id, value=message)
                    future.get(timeout=10)
                    messages_sent += 1
                except Exception as e:
                    errors += 1
                    print(f"  Error sending message: {e}")
                
                # Collect metrics periodically
                if time.time() - last_metrics_time >= 10.0:
                    metrics = collector.collect_all_metrics(duration=2.0)
                    metrics['messages_sent'] = messages_sent
                    metrics['errors'] = errors
                    test_metrics.append(metrics)
                    last_metrics_time = time.time()
                
                # Rate limiting
                elapsed = time.time() - message_start
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            # Final metrics collection
            final_metrics = collector.collect_all_metrics(duration=5.0)
            test_metrics.append(final_metrics)
            
            # Calculate averages
            if test_metrics:
                avg_spark_lag = sum(m['kafka'].get('spark_consumer_lag', 0) for m in test_metrics) / len(test_metrics)
                avg_ray_lag = sum(m['kafka'].get('ray_consumer_lag', 0) for m in test_metrics) / len(test_metrics)
                actual_rate = messages_sent / duration
                
                # Get max lag (worst case)
                max_spark_lag = max(m['kafka'].get('spark_consumer_lag', 0) for m in test_metrics)
                max_ray_lag = max(m['kafka'].get('ray_consumer_lag', 0) for m in test_metrics)
            else:
                avg_spark_lag = 0
                avg_ray_lag = 0
                actual_rate = 0
                max_spark_lag = 0
                max_ray_lag = 0
            
            test_result = {
                'target_rate': rate,
                'actual_rate': actual_rate,
                'messages_sent': messages_sent,
                'errors': errors,
                'avg_spark_consumer_lag': avg_spark_lag,
                'avg_ray_consumer_lag': avg_ray_lag,
                'max_spark_consumer_lag': max_spark_lag,
                'max_ray_consumer_lag': max_ray_lag,
                'rate_accuracy': (actual_rate / rate * 100) if rate > 0 else 0
            }
            
            results['tests'].append(test_result)
            
            print(f"\nResults for {rate} msg/sec:")
            print(f"  Messages Sent: {messages_sent}")
            print(f"  Actual Rate: {actual_rate:.2f} msg/sec")
            print(f"  Rate Accuracy: {test_result['rate_accuracy']:.1f}%")
            print(f"  Avg Spark Lag: {avg_spark_lag:.0f} messages")
            print(f"  Avg Ray Lag: {avg_ray_lag:.0f} messages")
            print(f"  Max Spark Lag: {max_spark_lag:.0f} messages")
            print(f"  Max Ray Lag: {max_ray_lag:.0f} messages")
            
            # Wait between tests
            if rate != rates_list[-1]:
                print("\nWaiting 10 seconds before next test...")
                time.sleep(10)
    
    finally:
        producer.flush()
        producer.close()
        admin_client.close()
    
    # Save results
    results_file = results_dir / 'load_scaling_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    return results
