"""
General configuration and environment variable management.
"""

import os
from typing import Optional

# Service URLs and ports
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
SPARK_MASTER_URL = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
RAY_HEAD_ADDRESS = os.getenv("RAY_HEAD_ADDRESS", "ray-head:6379")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))

# Spark configuration
SPARK_CHECKPOINT_LOCATION = os.getenv("SPARK_CHECKPOINT_LOCATION", "/app/checkpoints")
SPARK_WINDOW_DURATION = os.getenv("SPARK_WINDOW_DURATION", "5 minutes")
SPARK_SLIDE_DURATION = os.getenv("SPARK_SLIDE_DURATION", "1 minute")
SPARK_WATERMARK_DELAY = os.getenv("SPARK_WATERMARK_DELAY", "10 minutes")
SPARK_TRIGGER_INTERVAL = os.getenv("SPARK_TRIGGER_INTERVAL", "1 minute")

# Model storage
MODEL_STORAGE_PATH = os.getenv("MODEL_STORAGE_PATH", "/app/models")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # development, production

def get_kafka_bootstrap_servers() -> str:
    """Get Kafka bootstrap servers."""
    return KAFKA_BOOTSTRAP_SERVERS

def get_spark_master_url() -> str:
    """Get Spark master URL."""
    return SPARK_MASTER_URL

def get_ray_head_address() -> str:
    """Get Ray head address."""
    return RAY_HEAD_ADDRESS

