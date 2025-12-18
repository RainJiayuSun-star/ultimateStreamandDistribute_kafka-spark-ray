"""
Window aggregation functions for Spark Structured Streaming.
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    mean, stddev, min as spark_min, max as spark_max, count,
    col, window, avg, first, last
)


def aggregate_weather_metrics(df: DataFrame, window_col: str = "window") -> DataFrame:
    """
    Aggregate weather metrics for a windowed DataFrame.
    
    Args:
        df: Spark DataFrame that is already grouped by window and station_id
        window_col: Name of the window column (default: "window")
    
    Returns:
        DataFrame with aggregated metrics per station and window
    """
    # df is already grouped, so just apply aggregations
    return df.agg(
        # Temperature aggregations
        avg("temperature").alias("temperature_mean"),
        stddev("temperature").alias("temperature_std"),
        spark_min("temperature").alias("temperature_min"),
        spark_max("temperature").alias("temperature_max"),
        
        # Humidity aggregations
        avg("humidity").alias("humidity_mean"),
        stddev("humidity").alias("humidity_std"),
        spark_min("humidity").alias("humidity_min"),
        spark_max("humidity").alias("humidity_max"),
        
        # Pressure aggregations
        avg("sea_level_pressure").alias("pressure_mean"),
        stddev("sea_level_pressure").alias("pressure_std"),
        spark_min("sea_level_pressure").alias("pressure_min"),
        spark_max("sea_level_pressure").alias("pressure_max"),
        
        # Wind speed aggregations
        avg("wind_speed").alias("wind_speed_mean"),
        stddev("wind_speed").alias("wind_speed_std"),
        spark_min("wind_speed").alias("wind_speed_min"),
        spark_max("wind_speed").alias("wind_speed_max"),
        
        # Wind direction aggregations (circular mean would be better, but using simple mean for now)
        avg("wind_direction").alias("wind_direction_mean"),
        
        # Precipitation aggregations
        avg("precipitation_last_hour").alias("precipitation_mean"),
        spark_max("precipitation_last_hour").alias("precipitation_max"),
        
        # Count of measurements in window
        count("*").alias("measurement_count"),
        
        # First and last timestamps in window
        first("timestamp").alias("window_first_timestamp"),
        last("timestamp").alias("window_last_timestamp")
    )


def aggregate_per_station(df: DataFrame) -> DataFrame:
    """
    Aggregate weather data per station (without windowing).
    Used for non-windowed aggregations if needed.
    
    Args:
        df: Spark DataFrame with weather data
    
    Returns:
        DataFrame with aggregated metrics per station
    """
    return df.groupBy("station_id").agg(
        avg("temperature").alias("avg_temperature"),
        avg("humidity").alias("avg_humidity"),
        avg("sea_level_pressure").alias("avg_pressure"),
        avg("wind_speed").alias("avg_wind_speed"),
        count("*").alias("total_measurements")
    )

