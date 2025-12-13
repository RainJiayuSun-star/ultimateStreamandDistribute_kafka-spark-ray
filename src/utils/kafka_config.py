"""
Kafka configuration constants and settings.
"""

# Kafka broker configuration
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"  # Use 'kafka:9092' in Docker, 'localhost:9092' for local testing

# Topic names
TOPIC_WEATHER_RAW = "weather-raw"
TOPIC_WEATHER_FEATURES = "weather-features"
TOPIC_WEATHER_PREDICTIONS = "weather-predictions"

# Topic partitions (all topics have 4 partitions)
TOPIC_PARTITIONS = 4

# Replication factor
REPLICATION_FACTOR = 1

# Consumer group names
CONSUMER_GROUP_SPARK = "spark-streaming-group"
CONSUMER_GROUP_RAY = "ray-ml-inference"
CONSUMER_GROUP_API = "dashboard-consumers"
CONSUMER_GROUP_DEBUG = "debug"

# Kafka producer/consumer settings
KAFKA_PRODUCER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "retries": 10,
    "acks": "all",  # Wait for all in-sync replicas
}

KAFKA_CONSUMER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "auto_offset_reset": "latest",  # Start from latest messages
    "enable_auto_commit": True,
}

