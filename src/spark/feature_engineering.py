"""
Feature engineering functions for weather data.
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, lag, when, isnan, isnull, lit,
    unix_timestamp, lead, abs as spark_abs, avg
)
from pyspark.sql.window import Window


def calculate_rate_of_change(df: DataFrame, metric_col: str, time_col: str = "timestamp") -> DataFrame:
    """
    Calculate rate of change for a metric over time.
    
    Args:
        df: Spark DataFrame with weather data
        metric_col: Name of the metric column (e.g., "temperature")
        time_col: Name of the timestamp column
    
    Returns:
        DataFrame with rate_of_change column added
    """
    window_spec = Window.partitionBy("station_id").orderBy(time_col)
    
    # Convert timestamp to unix timestamp for calculation
    df_with_unix = df.withColumn(
        "unix_time",
        unix_timestamp(col(time_col))
    )
    
    # Calculate rate of change: (current - previous) / time_diff
    df_with_rate = df_with_unix.withColumn(
        f"{metric_col}_previous",
        lag(metric_col, 1).over(window_spec)
    ).withColumn(
        f"{metric_col}_time_previous",
        lag("unix_time", 1).over(window_spec)
    ).withColumn(
        f"{metric_col}_rate_of_change",
        when(
            (col(f"{metric_col}_previous").isNotNull()) & 
            (col(f"{metric_col}_time_previous").isNotNull()),
            (col(metric_col) - col(f"{metric_col}_previous")) / 
            (col("unix_time") - col(f"{metric_col}_time_previous"))
        ).otherwise(lit(0.0))
    )
    
    # Drop intermediate columns
    return df_with_rate.drop(
        f"{metric_col}_previous",
        f"{metric_col}_time_previous",
        "unix_time"
    )


def detect_trend(df: DataFrame, metric_col: str, window_size: int = 3) -> DataFrame:
    """
    Detect trend (increasing/decreasing) for a metric.
    Uses a simple moving average comparison.
    
    Args:
        df: Spark DataFrame with weather data
        metric_col: Name of the metric column
        window_size: Number of previous values to consider
    
    Returns:
        DataFrame with trend column added (1 = increasing, -1 = decreasing, 0 = stable)
    """
    window_spec = Window.partitionBy("station_id").orderBy("timestamp").rowsBetween(-window_size, 0)
    
    df_with_trend = df.withColumn(
        f"{metric_col}_recent_avg",
        avg(metric_col).over(window_spec)
    ).withColumn(
        f"{metric_col}_previous_avg",
        lag(avg(metric_col).over(window_spec), window_size).over(
            Window.partitionBy("station_id").orderBy("timestamp")
        )
    ).withColumn(
        f"{metric_col}_trend",
        when(
            col(f"{metric_col}_previous_avg").isNotNull(),
            when(
                col(f"{metric_col}_recent_avg") > col(f"{metric_col}_previous_avg"),
                lit(1)  # Increasing
            ).when(
                col(f"{metric_col}_recent_avg") < col(f"{metric_col}_previous_avg"),
                lit(-1)  # Decreasing
            ).otherwise(lit(0))  # Stable
        ).otherwise(lit(0))
    )
    
    return df_with_trend.drop(
        f"{metric_col}_recent_avg",
        f"{metric_col}_previous_avg"
    )


def add_derived_features(df: DataFrame) -> DataFrame:
    """
    Add derived weather features like heat index, wind chill, etc.
    
    Args:
        df: Spark DataFrame with weather data
    
    Returns:
        DataFrame with derived features added
    """
    # Heat Index (simplified formula, requires temperature in Fahrenheit and humidity)
    # HI = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH - ...
    # Using simplified version for now
    df_with_features = df.withColumn(
        "heat_index",
        when(
            (col("temperature") > 80) & (col("humidity") > 40),
            col("temperature") + 0.5 * (col("temperature") + col("humidity"))
        ).otherwise(col("temperature"))
    )
    
    # Wind Chill (simplified, requires temperature in Fahrenheit and wind speed)
    # WC = 35.74 + 0.6215*T - 35.75*V^0.16 + 0.4275*T*V^0.16
    df_with_features = df_with_features.withColumn(
        "wind_chill",
        when(
            (col("temperature") < 50) & (col("wind_speed") > 3),
            lit(35.74) + 
            lit(0.6215) * col("temperature") - 
            lit(35.75) * pow(col("wind_speed"), 0.16) +
            lit(0.4275) * col("temperature") * pow(col("wind_speed"), 0.16)
        ).otherwise(col("temperature"))
    )
    
    # Pressure change rate (if we have time series)
    window_spec = Window.partitionBy("station_id").orderBy("timestamp")
    df_with_features = df_with_features.withColumn(
        "pressure_change",
        col("sea_level_pressure") - lag("sea_level_pressure", 1).over(window_spec)
    )
    
    return df_with_features


def handle_null_values(df: DataFrame) -> DataFrame:
    """
    Handle null/missing values in weather data.
    
    Args:
        df: Spark DataFrame with weather data
    
    Returns:
        DataFrame with null values handled
    """
    return df.fillna({
        "temperature": 0.0,
        "humidity": 0.0,
        "wind_speed": 0.0,
        "wind_direction": 0.0,
        "sea_level_pressure": 1013.25,  # Standard atmospheric pressure
        "precipitation_last_hour": 0.0
    })

