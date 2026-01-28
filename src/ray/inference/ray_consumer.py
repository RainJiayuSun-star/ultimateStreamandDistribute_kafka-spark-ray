"""
Kafka consumer for Ray ML inference.
Consumes aggregated features from weather-features topic,
performs ML inference using Ray actors, and publishes predictions
to weather-predictions topic.
"""

import os
import sys
import json
import time
import logging
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
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    src_path = os.path.join(project_root, 'src')
    sys.path.insert(0, src_path)

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from utils.config import (
    RAY_HEAD_ADDRESS,
    RAY_CLIENT_URL,
    MODEL_STORAGE_PATH,
    HORIZON_HOURS,
    LOG_LEVEL,
    LOG_FORMAT
)
from utils.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TOPIC_WEATHER_FEATURES,
    TOPIC_WEATHER_PREDICTIONS,
    CONSUMER_GROUP_RAY,
    KAFKA_PRODUCER_CONFIG,
    KAFKA_CONSUMER_CONFIG
)
# Import from local ray module - use importlib to load directly from file
# This avoids conflict with the already-imported Ray package
import importlib.util

# Ensure /app/src is in sys.path before loading inference_actor
# (inference_actor.py also does this, but we need it here too for the imports inside it)
if os.path.exists('/app/src') and '/app/src' not in sys.path:
    sys.path.insert(0, '/app/src')
elif not os.path.exists('/app/src'):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

_inference_actor_file = os.path.join(os.path.dirname(__file__), 'inference_actor.py')
spec = importlib.util.spec_from_file_location("ray.inference.inference_actor", _inference_actor_file)
_inference_actor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_inference_actor_module)
InferenceActor = _inference_actor_module.InferenceActor

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)


class RayInferenceConsumer:
    """
    Kafka consumer that uses Ray actors for ML inference.
    """
    
    def __init__(
        self,
        model_name: str = "LSTM_FineTuned_20260124_193541",
        num_actors: int = 4,
        use_gpu: bool = False
    ):
        """
        Initialize Ray inference consumer.
        
        Args:
            model_name: Name of the model to load
            num_actors: Number of Ray inference actors to create
            use_gpu: Whether to use GPU for inference
        """
        self.model_name = model_name
        self.num_actors = num_actors
        self.use_gpu = use_gpu
        self.actors = []
        self.actor_index = 0
        
        # Initialize Ray connection
        self._connect_ray()
        
        # Create inference actors
        self._create_actors()
        
        # Initialize Kafka consumer and producer
        self.consumer = None
        self.producer = None
        self._init_kafka()
        
        logger.info("RayInferenceConsumer initialized")
    
    def _connect_ray(self):
        """Connect to Ray cluster via Ray Client (ray://) to avoid node_ip_address.json issue."""
        import socket
        import time
        
        try:
            if ray.is_initialized():
                logger.info("Ray already initialized")
                return
            
            # Use Ray Client (ray://) when RAY_CLIENT_URL is set - avoids node_ip_address.json
            # error when connecting from ray-inference container to ray-head.
            use_client = RAY_CLIENT_URL and RAY_CLIENT_URL.startswith("ray://")
            
            if use_client:
                # Parse ray://host:port for connectivity check
                parts = RAY_CLIENT_URL.replace("ray://", "").strip("/").split(":")
                ray_host = parts[0] if parts else "ray-head"
                ray_port = int(parts[1]) if len(parts) > 1 else 10001
                logger.info(f"Using Ray Client at {RAY_CLIENT_URL}")
            else:
                ray_host, ray_port = RAY_HEAD_ADDRESS.split(":")
                ray_port = int(ray_port)
            
            logger.info(f"Checking connectivity to {ray_host}:{ray_port}...")
            for i in range(15):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((ray_host, ray_port))
                    sock.close()
                    if result == 0:
                        logger.info(f"Ray server reachable at {ray_host}:{ray_port}")
                        break
                    raise ConnectionError(f"Cannot reach {ray_host}:{ray_port}")
                except (ConnectionError, socket.gaierror, OSError) as e:
                    if i < 14:
                        logger.warning(f"Not reachable ({i+1}/15), retrying in 3s: {e}")
                        time.sleep(3)
                    else:
                        raise
            
            # Brief wait for server to accept clients
            time.sleep(5)
            
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Connecting to Ray (attempt {attempt + 1}/{max_attempts})...")
                    if use_client:
                        ray.init(
                            RAY_CLIENT_URL,
                            ignore_reinit_error=True,
                            logging_level=logging.WARNING,
                        )
                    else:
                        ray.init(
                            address=RAY_HEAD_ADDRESS,
                            ignore_reinit_error=True,
                            logging_level=logging.WARNING,
                        )
                    logger.info("Connected to Ray cluster")
                    try:
                        res = ray.cluster_resources()
                        logger.info(f"Cluster resources: {res}")
                    except Exception as e:
                        logger.warning(f"Could not get cluster resources: {e}")
                    return
                except Exception as e:
                    if attempt < max_attempts - 1:
                        wait = 10 * (attempt + 1)
                        logger.warning(f"Connection failed: {e}. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Failed to connect to Ray: {e}")
            use = RAY_CLIENT_URL and str(RAY_CLIENT_URL).startswith("ray://")
            addr = RAY_CLIENT_URL if use else RAY_HEAD_ADDRESS
            logger.error(f"Ensure Ray is running and reachable at {addr}")
            raise
    
    def _create_actors(self):
        """Create Ray inference actors."""
        logger.info(f"Creating {self.num_actors} inference actors...")
        
        self.actors = []
        for i in range(self.num_actors):
            try:
                actor = InferenceActor.remote(
                    model_name=self.model_name,
                    use_gpu=self.use_gpu,
                    gpu_id=0  # All actors share the same GPU with fractional allocation
                )
                self.actors.append(actor)
                logger.info(f"Created inference actor {i+1}/{self.num_actors}")
                
                # Wait a bit between actor creation to avoid resource contention
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to create actor {i+1}: {e}")
                raise
        
        # Verify actors are healthy
        for i, actor in enumerate(self.actors):
            try:
                health = ray.get(actor.health_check.remote())
                logger.info(f"Actor {i+1} health: {health}")
            except Exception as e:
                logger.warning(f"Actor {i+1} health check failed: {e}")
        
        logger.info(f"Successfully created {len(self.actors)} inference actors")
    
    def _init_kafka(self):
        """Initialize Kafka consumer and producer."""
        try:
            # Create consumer
            consumer_config = KAFKA_CONSUMER_CONFIG.copy()
            consumer_config['group_id'] = CONSUMER_GROUP_RAY
            
            self.consumer = KafkaConsumer(
                TOPIC_WEATHER_FEATURES,
                **consumer_config,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None
            )
            logger.info(f"Kafka consumer initialized for topic: {TOPIC_WEATHER_FEATURES}")
            
            # Create producer
            self.producer = KafkaProducer(
                **KAFKA_PRODUCER_CONFIG,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            logger.info(f"Kafka producer initialized for topic: {TOPIC_WEATHER_PREDICTIONS}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            raise
    
    def _get_next_actor(self) -> InferenceActor:
        """
        Get next actor using round-robin selection.
        
        Returns:
            Next inference actor
        """
        actor = self.actors[self.actor_index]
        self.actor_index = (self.actor_index + 1) % len(self.actors)
        return actor
    
    def _process_message(self, message) -> Optional[Dict[str, Any]]:
        """
        Process a single Kafka message and generate predictions.
        
        Args:
            message: Kafka message object
        
        Returns:
            Dictionary with predictions or None if processing failed
        """
        try:
            # Parse message
            features = message.value
            station_id = message.key if message.key else features.get('station_id', 'UNKNOWN')
            
            logger.debug(f"Processing message for station: {station_id}")
            
            # Get actor for inference
            actor = self._get_next_actor()
            
            # Perform inference (async). Horizon capped at 7h in model (recursive 24h disabled).
            future = actor.predict.remote(features, HORIZON_HOURS)
            result = ray.get(future, timeout=30.0)
            
            # Format prediction result
            prediction = {
                'station_id': station_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'window_start': features.get('window_start'),
                'window_end': features.get('window_end'),
                'forecast': result.get('forecast', {}),
                'horizon_hours': result.get('horizon_hours', HORIZON_HOURS),
                'current_conditions': {
                    'temperature_mean': features.get('temperature_mean'),
                    'humidity_mean': features.get('humidity_mean'),
                    'pressure_mean': features.get('pressure_mean'),
                    'wind_speed_mean': features.get('wind_speed_mean'),
                }
            }
            
            logger.info(f"Generated predictions for station: {station_id}")
            return prediction
            
        except ray.exceptions.GetTimeoutError:
            logger.error(f"Inference timeout for message")
            return None
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _publish_prediction(self, prediction: Dict[str, Any]):
        """
        Publish prediction to Kafka.
        
        Args:
            prediction: Dictionary with prediction data
        """
        try:
            station_id = prediction.get('station_id', 'UNKNOWN')
            
            # Publish to Kafka
            future = self.producer.send(
                TOPIC_WEATHER_PREDICTIONS,
                key=station_id,
                value=prediction
            )
            
            # Wait for confirmation (with timeout)
            record_metadata = future.get(timeout=10.0)
            
            logger.debug(
                f"Published prediction for {station_id} "
                f"to partition {record_metadata.partition}, "
                f"offset {record_metadata.offset}"
            )
            
        except Exception as e:
            logger.error(f"Failed to publish prediction: {e}")
    
    def run(self):
        """Main consumption loop."""
        logger.info("Starting Ray inference consumer...")
        logger.info(f"Consuming from: {TOPIC_WEATHER_FEATURES}")
        logger.info(f"Publishing to: {TOPIC_WEATHER_PREDICTIONS}")
        
        message_count = 0
        
        try:
            # Wait for partition assignment
            logger.info("Waiting for partition assignment...")
            _ = self.consumer.poll(timeout_ms=5000)
            
            assigned_partitions = self.consumer.assignment()
            logger.info(f"Assigned to partitions: {assigned_partitions}")
            
            # Main consumption loop
            logger.info("Starting message consumption...")
            for message in self.consumer:
                try:
                    message_count += 1
                    logger.debug(f"Received message #{message_count}")
                    
                    # Process message
                    prediction = self._process_message(message)
                    
                    if prediction:
                        # Publish prediction
                        self._publish_prediction(prediction)
                        logger.info(f"Processed message #{message_count} successfully")
                    else:
                        logger.warning(f"Failed to process message #{message_count}")
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            raise
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources...")
        
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")
        
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")
        
        if ray.is_initialized():
            ray.shutdown()
            logger.info("Ray connection closed")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ray ML Inference Consumer')
    parser.add_argument(
        '--model-name',
        type=str,
        default='LSTM_FineTuned_20260124_193541',
        help='Model name to load'
    )
    parser.add_argument(
        '--num-actors',
        type=int,
        default=4,
        help='Number of Ray inference actors'
    )
    parser.add_argument(
        '--no-gpu',
        action='store_true',
        help='Disable GPU usage'
    )
    
    args = parser.parse_args()
    
    # Create and run consumer
    consumer = RayInferenceConsumer(
        model_name=args.model_name,
        num_actors=args.num_actors,
        use_gpu=not args.no_gpu
    )
    
    try:
        consumer.run()
    except Exception as e:
        logger.error(f"Consumer failed: {e}")
        raise


if __name__ == '__main__':
    main()

