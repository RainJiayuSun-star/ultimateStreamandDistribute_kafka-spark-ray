"""
Main Kafka consumer for Ray ML inference.
Consumes from weather-features topic, performs inference using Ray actors,
and writes results to weather-predictions topic.
"""

import json
import logging
import sys
import time
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

import ray
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ray.inference.inference_actor import InferenceActor
except ImportError:
    from inference.inference_actor import InferenceActor

# Import configuration
try:
    from utils.kafka_config import (
        KAFKA_BOOTSTRAP_SERVERS,
        TOPIC_WEATHER_FEATURES,
        TOPIC_WEATHER_PREDICTIONS,
        CONSUMER_GROUP_RAY
    )
    from utils.config import RAY_HEAD_ADDRESS
except ImportError:
    # Fallback if running from different location
    sys.path.insert(0, '/app')
    from utils.kafka_config import (
        KAFKA_BOOTSTRAP_SERVERS,
        TOPIC_WEATHER_FEATURES,
        TOPIC_WEATHER_PREDICTIONS,
        CONSUMER_GROUP_RAY
    )
    from utils.config import RAY_HEAD_ADDRESS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def connect_to_ray(ray_address: str, max_retries: int = 10) -> bool:
    """
    Connect to Ray cluster.
    
    Args:
        ray_address: Ray head address (e.g., "ray-head:6379")
        max_retries: Maximum number of connection retries
    
    Returns:
        True if connected successfully, False otherwise
    """
    for attempt in range(max_retries):
        try:
            ray.init(address=ray_address, ignore_reinit_error=True)
            logger.info(f"Successfully connected to Ray cluster at {ray_address}")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Ray (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logger.error("Failed to connect to Ray cluster after all retries")
                return False
    return False


def create_inference_actors(num_actors: int = 2) -> List:
    """
    Create Ray inference actors.
    
    Args:
        num_actors: Number of inference actors to create
    
    Returns:
        List of actor handles
    """
    actors = []
    for i in range(num_actors):
        try:
            actor = InferenceActor.remote()
            # Test actor health
            health = ray.get(actor.health_check.remote())
            logger.info(f"Created inference actor {i+1}/{num_actors}: {health}")
            actors.append(actor)
        except Exception as e:
            logger.error(f"Error creating inference actor {i+1}: {e}")
    
    if not actors:
        logger.error("Failed to create any inference actors!")
        sys.exit(1)
    
    logger.info(f"Successfully created {len(actors)} inference actors")
    return actors


def format_prediction_for_kafka(prediction_result: Dict) -> Dict:
    """
    Format prediction result for Kafka output.
    
    Args:
        prediction_result: Result from inference actor
    
    Returns:
        Formatted dictionary for Kafka
    """
    return {
        'station_id': prediction_result.get('station_id', 'UNKNOWN'),
        'timestamp': datetime.utcnow().isoformat(),
        'window_start': prediction_result.get('window_start', ''),
        'window_end': prediction_result.get('window_end', ''),
        'forecast': prediction_result.get('forecast', {}),
        'anomaly': prediction_result.get('anomaly', {}),
        'current_conditions': prediction_result.get('current_conditions', {}),
        'prediction_timestamp': datetime.utcnow().isoformat()
    }


def main():
    """
    Main function: consume from Kafka, perform inference, write results.
    """
    logger.info("=" * 80)
    logger.info("Starting Ray ML Inference Consumer")
    logger.info("=" * 80)
    
    # Connect to Ray cluster
    logger.info(f"Connecting to Ray cluster at {RAY_HEAD_ADDRESS}...")
    if not connect_to_ray(RAY_HEAD_ADDRESS):
        logger.error("Failed to connect to Ray cluster. Exiting.")
        sys.exit(1)
    
    # Create inference actors
    logger.info("Creating inference actors...")
    actors = create_inference_actors(num_actors=2)  # Use 2 actors for parallel processing
    actor_index = 0  # Round-robin assignment
    
    # Initialize Kafka consumer
    logger.info(f"Initializing Kafka consumer for topic: {TOPIC_WEATHER_FEATURES}")
    logger.info(f"Consumer group: {CONSUMER_GROUP_RAY}")
    
    consumer = None
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            consumer = KafkaConsumer(
                TOPIC_WEATHER_FEATURES,
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                group_id=CONSUMER_GROUP_RAY,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None
            )
            logger.info("Kafka consumer initialized successfully")
            break
        except NoBrokersAvailable:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Kafka broker not available, retrying ({retry_count}/{max_retries})...")
                time.sleep(2)
            else:
                logger.error("Failed to connect to Kafka after all retries")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error initializing Kafka consumer: {e}")
            sys.exit(1)
    
    # Initialize Kafka producer
    logger.info(f"Initializing Kafka producer for topic: {TOPIC_WEATHER_PREDICTIONS}")
    
    producer = None
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                retries=10,
                acks='all',
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            logger.info("Kafka producer initialized successfully")
            break
        except NoBrokersAvailable:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Kafka broker not available for producer, retrying ({retry_count}/{max_retries})...")
                time.sleep(2)
            else:
                logger.error("Failed to connect to Kafka producer after all retries")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error initializing Kafka producer: {e}")
            sys.exit(1)
    
    # Wait for partition assignment
    logger.info("Waiting for partition assignment...")
    _ = consumer.poll(timeout_ms=5000)
    logger.info(f"Consumer assigned to partitions: {consumer.assignment()}")
    
    logger.info("=" * 80)
    logger.info("Starting inference loop...")
    logger.info("=" * 80)
    
    message_count = 0
    
    try:
        for message in consumer:
            try:
                # Get features from Kafka message
                features = message.value
                station_id = message.key if message.key else features.get('station_id', 'UNKNOWN')
                
                logger.debug(f"Received features for station: {station_id}")
                
                # Ensure station_id is in features
                features['station_id'] = station_id
                
                # Select actor (round-robin)
                actor = actors[actor_index]
                actor_index = (actor_index + 1) % len(actors)
                
                # Perform inference using Ray actor
                logger.debug(f"Performing inference for station: {station_id}")
                prediction_result = ray.get(actor.predict.remote(features))
                
                # Check for errors
                if 'error' in prediction_result:
                    logger.error(f"Error in prediction for {station_id}: {prediction_result['error']}")
                    continue
                
                # Format result for Kafka
                kafka_message = format_prediction_for_kafka(prediction_result)
                
                # Write to Kafka
                future = producer.send(
                    TOPIC_WEATHER_PREDICTIONS,
                    key=station_id,
                    value=kafka_message
                )
                
                # Wait for send to complete
                record_metadata = future.get(timeout=10)
                
                message_count += 1
                logger.info(
                    f"[{message_count}] Prediction for {station_id}: "
                    f"Anomaly={prediction_result['anomaly']['is_anomaly']}, "
                    f"Score={prediction_result['anomaly']['score']:.3f}, "
                    f"Published to partition {record_metadata.partition}"
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Error deserializing JSON message: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                continue
    
    except KeyboardInterrupt:
        logger.info("\nShutting down Ray consumer...")
    except Exception as e:
        logger.error(f"Fatal error in consumer loop: {e}", exc_info=True)
    finally:
        if consumer:
            consumer.close()
        if producer:
            producer.flush()
            producer.close()
        ray.shutdown()
        logger.info(f"Processed {message_count} messages. Ray consumer shut down.")


if __name__ == "__main__":
    main()

