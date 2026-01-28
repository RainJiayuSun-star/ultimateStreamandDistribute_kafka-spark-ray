"""
Test script for Ray ML inference pipeline.
Consumes aggregated features from weather-features topic,
performs ML inference using Ray actors, and displays predictions.

This tester verifies that:
1. Ray inference actors can be created and loaded
2. Models can be loaded successfully
3. Inference can be performed on Spark aggregated features
4. Predictions are generated correctly

Commands to run:
- In Docker (src/ is mounted to /app/src/)
docker exec -it ray-head python3 /app/src/testers/test_ray_inference.py

- Local testing
python3 src/testers/test_ray_inference.py
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

# CRITICAL: Import Ray package BEFORE adding local ray module to path
# Temporarily remove /app/src from path to ensure we import the installed Ray package
original_path = sys.path[:]
src_path_to_remove = None

if os.path.exists('/app/src'):
    # Docker environment
    if '/app/src' in sys.path:
        sys.path.remove('/app/src')
        src_path_to_remove = '/app/src'
else:
    # Local environment - find and temporarily remove src path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_path = os.path.join(project_root, 'src')
    if src_path in sys.path:
        sys.path.remove(src_path)
        src_path_to_remove = src_path

# Now import Ray package (will find installed package, not local directory)
import ray

# Restore src path and add it back for local module imports
if src_path_to_remove:
    sys.path.insert(0, src_path_to_remove)
elif os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_path = os.path.join(project_root, 'src')
    sys.path.insert(0, src_path)

from kafka import KafkaConsumer
import importlib.util

# Import configuration
from utils.config import RAY_HEAD_ADDRESS, LOG_LEVEL, HORIZON_HOURS
from utils.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TOPIC_WEATHER_FEATURES,
    KAFKA_CONSUMER_CONFIG
)

# Load InferenceActor using importlib to avoid conflicts with installed ray package
if os.path.exists('/app/src'):
    inference_actor_path = '/app/src/ray/inference/inference_actor.py'
else:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    inference_actor_path = os.path.join(project_root, 'src', 'ray', 'inference', 'inference_actor.py')

spec = importlib.util.spec_from_file_location("inference_actor", inference_actor_path)
inference_actor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inference_actor_module)
InferenceActor = inference_actor_module.InferenceActor

# Configuration
broker = KAFKA_BOOTSTRAP_SERVERS  # 'kafka:9092' in Docker, 'localhost:9092' for local
topic_name = TOPIC_WEATHER_FEATURES
group_id = 'ray-inference-test-group'

# Choose offset strategy: 'earliest' to see all messages, 'latest' to see only new ones
OFFSET_STRATEGY = 'earliest'  # Options: 'earliest' or 'latest'

# Ray configuration
MODEL_NAME = 'LSTM_FineTuned_20260124_193541'
NUM_ACTORS = 2  # Use fewer actors for testing
USE_GPU = False  # CPU-only mode


def connect_ray():
    """Connect to Ray cluster."""
    import socket
    
    try:
        if ray.is_initialized():
            print("✓ Ray already initialized")
            return
        
        # Verify Ray head is reachable
        ray_host, ray_port = RAY_HEAD_ADDRESS.split(":")
        ray_port = int(ray_port)
        
        print(f"Checking connectivity to Ray head at {ray_host}:{ray_port}...")
        max_retries = 10
        for i in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ray_host, ray_port))
                sock.close()
                if result == 0:
                    print(f"✓ Ray head is reachable at {ray_host}:{ray_port}")
                    break
                else:
                    if i < max_retries - 1:
                        print(f"  Retrying ({i+1}/{max_retries})...")
                        time.sleep(2)
                    else:
                        raise ConnectionError(f"Cannot reach Ray head at {ray_host}:{ray_port}")
            except socket.gaierror as e:
                raise ConnectionError(f"Cannot resolve Ray head hostname '{ray_host}': {e}")
        
        # Check if Ray dashboard is accessible (indicates GCS is ready)
        print("Waiting for Ray head GCS to be fully ready...")
        dashboard_port = 8265
        dashboard_ready = False
        for i in range(20):  # Wait up to 20 seconds for dashboard
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ray_host, dashboard_port))
                sock.close()
                if result == 0:
                    print(f"✓ Ray dashboard is accessible, GCS should be ready")
                    dashboard_ready = True
                    break
            except Exception:
                pass
            if i < 19:
                time.sleep(1)
        
        if not dashboard_ready:
            print("⚠ Ray dashboard not accessible yet, but proceeding with connection attempt...")
        
        # Additional wait to ensure GCS is fully ready
        time.sleep(5)
        
        # Connect with retry logic
        print(f"Connecting to Ray cluster at {RAY_HEAD_ADDRESS}...")
        max_connection_retries = 3
        for attempt in range(max_connection_retries):
            try:
                print(f"  Attempt {attempt + 1}/{max_connection_retries}...")
                ray.init(
                    address=RAY_HEAD_ADDRESS,
                    ignore_reinit_error=True,
                    logging_level=30  # WARNING level
                )
                print("✓ Connected to Ray cluster")
                # Verify connection
                try:
                    cluster_resources = ray.cluster_resources()
                    print(f"✓ Cluster resources: {len(cluster_resources)} nodes available")
                except Exception as e:
                    print(f"⚠ Could not get cluster resources: {e}")
                break
            except ValueError as e:
                if "node_ip_address.json" in str(e) and attempt < max_connection_retries - 1:
                    wait_time = 15 * (attempt + 1)
                    print(f"⚠ Connection timed out, waiting {wait_time}s and retrying...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                if attempt < max_connection_retries - 1:
                    wait_time = 15 * (attempt + 1)
                    print(f"⚠ Connection failed: {e}, waiting {wait_time}s and retrying...")
                    time.sleep(wait_time)
                else:
                    raise
        
    except Exception as e:
        print(f"✗ Failed to connect to Ray cluster: {e}")
        print("\nTroubleshooting:")
        print("  1. Check Ray head is running: docker ps | grep ray-head")
        print("  2. Check Ray logs: docker logs ray-head")
        print("  3. Verify network: docker exec ray-head ping ray-head")
        print("  4. Check Ray dashboard: http://localhost:8265")
        raise


def create_inference_actors(num_actors: int = NUM_ACTORS) -> list:
    """Create Ray inference actors."""
    print(f"\nCreating {num_actors} inference actors...")
    actors = []
    
    for i in range(num_actors):
        try:
            print(f"  Creating actor {i+1}/{num_actors}...", end=' ')
            actor = InferenceActor.remote(
                model_name=MODEL_NAME,
                use_gpu=USE_GPU
            )
            actors.append(actor)
            
            # Wait a bit for initialization
            time.sleep(2)
            
            # Check health
            health = ray.get(actor.health_check.remote(), timeout=10.0)
            if health.get('model_loaded'):
                print(f"✓ (Model loaded: {health.get('model_name')})")
            else:
                print(f"⚠ (Model not loaded)")
                
        except Exception as e:
            print(f"✗ Failed: {e}")
            raise
    
    print(f"✓ Successfully created {len(actors)} inference actors\n")
    return actors


def format_prediction_output(
    station_id: str,
    features: Dict[str, Any],
    prediction: Dict[str, Any],
    inference_time: float
) -> str:
    """Format prediction output for display."""
    output = []
    output.append("=" * 80)
    output.append(f"Station: {station_id}")
    output.append(f"Inference Time: {inference_time*1000:.1f}ms")
    output.append("=" * 80)
    
    # Input features
    output.append("\n📥 Input Features (from Spark):")
    output.append(f"  Window: {features.get('window_start', 'N/A')} to {features.get('window_end', 'N/A')}")
    output.append(f"  Measurements: {features.get('measurement_count', 'N/A')}")
    output.append(f"  Temperature Mean: {features.get('temperature_mean', 'N/A')}°C (metric - matches model training)")
    output.append(f"  Humidity Mean: {features.get('humidity_mean', 'N/A')}%")
    output.append(f"  Pressure Mean: {features.get('pressure_mean', 'N/A')} hPa")
    output.append(f"  Wind Speed Mean: {features.get('wind_speed_mean', 'N/A')} m/s (metric)")
    
    # Predictions
    forecast = prediction.get('forecast', {})
    if forecast:
        predictions = forecast.get('temperature_predictions', [])
        horizon = forecast.get('horizon_hours', len(predictions))
        
        output.append(f"\n📤 Temperature Forecast (next {horizon} hours) - in Celsius (metric):")
        if predictions:
            # List all hours (e.g. all 24 when horizon=24)
            output.append(f"  Next {horizon} hours:")
            for i, temp in enumerate(predictions):
                hour = i + 1
                temp_c = temp
                temp_f = (temp_c * 9/5) + 32
                output.append(f"    +{hour:2d}h: {temp_c:6.1f}°C ({temp_f:5.1f}°F)")
            
            # Overall statistics
            avg_temp = sum(predictions) / len(predictions)
            min_temp = min(predictions)
            max_temp = max(predictions)
            avg_temp_f = (avg_temp * 9/5) + 32
            min_temp_f = (min_temp * 9/5) + 32
            max_temp_f = (max_temp * 9/5) + 32
            current_temp = features.get('temperature_mean', 0)
            current_temp_f = (current_temp * 9/5) + 32 if current_temp else 0
            next_temp_f = (predictions[0] * 9/5) + 32
            output.append(f"\n  Forecast Statistics:")
            output.append(f"    Average: {avg_temp:.1f}°C ({avg_temp_f:.1f}°F)")
            output.append(f"    Range: {min_temp:.1f}°C to {max_temp:.1f}°C ({min_temp_f:.1f}°F to {max_temp_f:.1f}°F)")
            output.append(f"    Current → +1h: {current_temp:.1f}°C ({current_temp_f:.1f}°F) → {predictions[0]:.1f}°C ({next_temp_f:.1f}°F)")
        else:
            output.append("  ⚠ No predictions generated")
    else:
        output.append("\n⚠ No forecast data in prediction")
    
    output.append("-" * 80)
    return "\n".join(output)


def main():
    """Main test function."""
    print("=" * 80)
    print("Ray ML Inference Pipeline Tester")
    print("=" * 80)
    print(f"Kafka Broker: {broker}")
    print(f"Topic: {topic_name}")
    print(f"Model: {MODEL_NAME}")
    print(f"Ray Address: {RAY_HEAD_ADDRESS}")
    print(f"GPU Enabled: {USE_GPU}")
    print("=" * 80)
    
    # Connect to Ray
    try:
        connect_ray()
    except Exception as e:
        print(f"\n✗ Failed to initialize Ray: {e}")
        print("\nMake sure Ray cluster is running:")
        print("  docker ps | grep ray-head")
        sys.exit(1)
    
    # Create inference actors
    try:
        actors = create_inference_actors(NUM_ACTORS)
        if not actors:
            print("✗ No actors created")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Failed to create actors: {e}")
        print("\nTroubleshooting:")
        print("  1. Check model exists: ls -la /app/models/trained/forecasting/")
        print("  2. Check Ray logs: docker logs ray-head")
        print("  3. Verify Ray cluster is running: docker ps | grep ray")
        sys.exit(1)
    
    # Initialize Kafka consumer
    print(f"\nInitializing Kafka consumer for topic '{topic_name}'...")
    try:
        consumer_config = KAFKA_CONSUMER_CONFIG.copy()
        consumer_config['group_id'] = group_id
        consumer_config['auto_offset_reset'] = OFFSET_STRATEGY
        
        consumer = KafkaConsumer(
            topic_name,
            **consumer_config,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None
        )
        print("✓ Kafka consumer initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Kafka consumer: {e}")
        print("\nTroubleshooting:")
        print("  1. Check Kafka is running: docker ps | grep kafka")
        print("  2. Check Kafka logs: docker logs kafka")
        sys.exit(1)
    
    # Wait for partition assignment
    print("\nWaiting for partition assignment...")
    _ = consumer.poll(timeout_ms=5000)
    assigned_partitions = consumer.assignment()
    print(f"✓ Assigned to partitions: {assigned_partitions}")
    
    if OFFSET_STRATEGY == 'earliest':
        print("✓ Using 'earliest' offset - will show all historical messages")
        # Check for existing messages
        for partition in assigned_partitions:
            try:
                consumer.seek(partition, 0)
            except:
                pass
        peek_messages = consumer.poll(timeout_ms=2000)
        if peek_messages:
            total = sum(len(msgs) for msgs in peek_messages.values())
            print(f"✓ Found {total} message(s) in topic")
        else:
            print("⚠ No messages found in topic yet")
    else:
        print("⚠ Using 'latest' offset - will only show NEW messages")
    
    print("\n" + "=" * 80)
    print("Starting inference testing...")
    print("Press Ctrl+C to stop")
    print("=" * 80 + "\n")
    
    # Main loop
    message_count = 0
    actor_index = 0
    total_inference_time = 0.0
    
    try:
        for message in consumer:
            try:
                # Parse message
                features = message.value
                station_id = message.key if message.key else features.get('station_id', 'UNKNOWN')
                
                message_count += 1
                
                # Get actor (round-robin)
                actor = actors[actor_index]
                actor_index = (actor_index + 1) % len(actors)
                
                # Perform inference
                start_time = time.time()
                try:
                    future = actor.predict.remote(features, HORIZON_HOURS)
                    prediction = ray.get(future, timeout=30.0)
                    inference_time = time.time() - start_time
                    total_inference_time += inference_time
                    
                    # Display results
                    output = format_prediction_output(
                        station_id,
                        features,
                        prediction,
                        inference_time
                    )
                    print(output)
                    
                    # Show progress
                    if message_count % 5 == 0:
                        avg_time = total_inference_time / message_count
                        print(f"\n[Progress] Processed {message_count} messages | "
                              f"Avg inference: {avg_time*1000:.1f}ms\n")
                    
                except ray.exceptions.GetTimeoutError:
                    print(f"\n⚠ Inference timeout for message #{message_count}")
                    print(f"  Station: {station_id}")
                    print(f"  This might indicate model loading issues or performance problems\n")
                    continue
                except Exception as e:
                    print(f"\n✗ Inference failed for message #{message_count}: {e}")
                    print(f"  Station: {station_id}\n")
                    import traceback
                    traceback.print_exc()
                    continue
                
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                print(f"\n✗ JSON decode error: {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"\n✗ Error processing message: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                continue
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("Stopped by user")
        print("=" * 80)
        if message_count > 0:
            avg_time = total_inference_time / message_count
            print(f"Total messages processed: {message_count}")
            print(f"Average inference time: {avg_time*1000:.1f}ms")
            print(f"Total inference time: {total_inference_time:.2f}s")
        else:
            print("No messages processed")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n✗ Consumer error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\nCleaning up...")
        consumer.close()
        if ray.is_initialized():
            ray.shutdown()
        print("✓ Cleanup complete")


if __name__ == '__main__':
    main()

