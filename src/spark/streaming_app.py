"""
Main Spark Structured Streaming application.
Reads from weather-raw topic, applies windowing and aggregations,
and writes aggregated features to weather-features topic.
"""

import json
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_json, struct, window, 
    current_timestamp, expr, to_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    TimestampType, IntegerType
)

# Import configuration
from utils.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TOPIC_WEATHER_RAW,
    TOPIC_WEATHER_FEATURES
)
from utils.config import (
    SPARK_CHECKPOINT_LOCATION,
    SPARK_WINDOW_DURATION,
    SPARK_SLIDE_DURATION,
    SPARK_WATERMARK_DELAY,
    SPARK_TRIGGER_INTERVAL
)

# Import aggregation and feature engineering functions
from spark.aggregations import aggregate_weather_metrics
from spark.feature_engineering import handle_null_values


# Define schema for weather-raw topic messages
WEATHER_RAW_SCHEMA = StructType([
    StructField("station_id", StringType(), True),
    StructField("station_name", StringType(), True),
    StructField("timestamp", StringType(), True),  # ISO format string
    StructField("temperature", DoubleType(), True),
    StructField("humidity", DoubleType(), True),
    StructField("wind_speed", DoubleType(), True),
    StructField("wind_direction", DoubleType(), True),
    StructField("sea_level_pressure", DoubleType(), True),
    StructField("precipitation_last_hour", DoubleType(), True),
])


def create_spark_session() -> SparkSession:
    """
    Create and configure Spark session for streaming.
    
    Returns:
        Configured SparkSession
    """
    spark = SparkSession.builder \
        .appName("WeatherStreamingApp") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.7") \
        .config("spark.sql.streaming.checkpointLocation", SPARK_CHECKPOINT_LOCATION) \
        .config("spark.sql.streaming.schemaInference", "true") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()
    
    # Set log level
    spark.sparkContext.setLogLevel("WARN")
    
    return spark


def read_from_kafka(spark: SparkSession) -> 'DataFrame':
    """
    Read streaming data from Kafka weather-raw topic.
    
    Args:
        spark: SparkSession
    
    Returns:
        DataFrame with Kafka message data
    """
    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", TOPIC_WEATHER_RAW) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()


def parse_kafka_messages(kafka_df) -> 'DataFrame':
    """
    Parse JSON messages from Kafka and extract weather data.
    
    Args:
        kafka_df: DataFrame from Kafka source
    
    Returns:
        DataFrame with parsed weather data
    """
    # Parse JSON value
    parsed_df = kafka_df.select(
        col("key").cast("string").alias("kafka_key"),
        from_json(col("value").cast("string"), WEATHER_RAW_SCHEMA).alias("data"),
        col("timestamp").alias("kafka_timestamp"),
        col("partition").alias("kafka_partition")
    ).select(
        "kafka_key",
        "data.*",
        "kafka_timestamp",
        "kafka_partition"
    )
    
    # Convert timestamp string to TimestampType
    parsed_df = parsed_df.withColumn(
        "timestamp",
        to_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ssXXX")
    )
    
    # Handle null values
    parsed_df = handle_null_values(parsed_df)
    
    return parsed_df


def apply_windowing_and_aggregation(df) -> 'DataFrame':
    """
    Apply sliding window and aggregate weather metrics.
    
    Args:
        df: DataFrame with parsed weather data
    
    Returns:
        DataFrame with aggregated features per window
    """
    # Apply sliding window with watermark and group by window and station_id
    windowed_df = df.withWatermark("timestamp", SPARK_WATERMARK_DELAY) \
        .groupBy(
            window(col("timestamp"), SPARK_WINDOW_DURATION, SPARK_SLIDE_DURATION),
            col("station_id")
        )
    
    # Aggregate metrics (aggregate_weather_metrics expects a grouped DataFrame)
    aggregated_df = aggregate_weather_metrics(windowed_df, "window")
    
    # Extract window start and end times
    aggregated_df = aggregated_df.withColumn(
        "window_start",
        col("window.start")
    ).withColumn(
        "window_end",
        col("window.end")
    ).drop("window")
    
    return aggregated_df


def format_for_kafka_output(df) -> 'DataFrame':
    """
    Format aggregated data for writing to Kafka.
    
    Args:
        df: DataFrame with aggregated features
    
    Returns:
        DataFrame formatted for Kafka output (with 'key' and 'value' columns)
    """
    # Select and format columns for output
    output_df = df.select(
        col("station_id"),
        col("window_start").cast("string").alias("window_start"),
        col("window_end").cast("string").alias("window_end"),
        col("temperature_mean"),
        col("temperature_std"),
        col("temperature_min"),
        col("temperature_max"),
        col("humidity_mean"),
        col("humidity_std"),
        col("humidity_min"),
        col("humidity_max"),
        col("pressure_mean"),
        col("pressure_std"),
        col("pressure_min"),
        col("pressure_max"),
        col("wind_speed_mean"),
        col("wind_speed_std"),
        col("wind_speed_min"),
        col("wind_speed_max"),
        col("wind_direction_mean"),
        col("precipitation_mean"),
        col("precipitation_max"),
        col("measurement_count"),
        col("window_first_timestamp").cast("string").alias("window_first_timestamp"),
        col("window_last_timestamp").cast("string").alias("window_last_timestamp")
    )
    
    # Convert to JSON for Kafka
    # Create a struct with all columns (excluding station_id which will be the key)
    # station_id is used as the key, so we include it in the value for completeness
    output_columns = [col(c) for c in output_df.columns]
    output_df = output_df.withColumn(
        "value",
        to_json(struct(*output_columns))
    ).select(
        col("station_id").cast("string").alias("key"),
        col("value")
    )
    
    return output_df


def main():
    """
    Main function to run Spark Structured Streaming application.
    """
    print("=" * 80)
    print("Starting Spark Structured Streaming Application")
    print("=" * 80)
    print(f"Reading from: {TOPIC_WEATHER_RAW}")
    print(f"Writing to: {TOPIC_WEATHER_FEATURES}")
    print(f"Window duration: {SPARK_WINDOW_DURATION}")
    print(f"Slide duration: {SPARK_SLIDE_DURATION}")
    print(f"Watermark delay: {SPARK_WATERMARK_DELAY}")
    print("=" * 80)
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Read from Kafka
        print("\n[1/4] Reading from Kafka...")
        kafka_df = read_from_kafka(spark)
        
        # Parse messages
        print("[2/4] Parsing JSON messages...")
        weather_df = parse_kafka_messages(kafka_df)
        
        # Apply windowing and aggregation
        print("[3/4] Applying windowing and aggregation...")
        aggregated_df = apply_windowing_and_aggregation(weather_df)
        
        # Format for Kafka output
        print("[4/4] Formatting for Kafka output...")
        output_df = format_for_kafka_output(aggregated_df)
        
        # Write to Kafka
        print("\nStarting streaming query...")
        query = output_df.writeStream \
            .outputMode("update") \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("topic", TOPIC_WEATHER_FEATURES) \
            .option("kafka.metadata.broker.list", KAFKA_BOOTSTRAP_SERVERS) \
            .option("checkpointLocation", f"{SPARK_CHECKPOINT_LOCATION}/kafka-output") \
            .trigger(processingTime=SPARK_TRIGGER_INTERVAL) \
            .start()
        
        print("Streaming query started successfully!")
        print("Waiting for termination...")
        
        # Wait for termination
        query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\nShutting down streaming application...")
    except Exception as e:
        print(f"Error in streaming application: {e}", file=sys.stderr)
        raise
    finally:
        spark.stop()
        print("Spark session stopped.")


if __name__ == "__main__":
    main()

