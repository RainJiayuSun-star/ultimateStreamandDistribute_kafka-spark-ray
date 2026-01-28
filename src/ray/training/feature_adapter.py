"""
Feature adapter to convert Spark aggregated features to raw features for model inference.
This allows training on raw historical data while inferring on Spark-aggregated data.
"""

import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class FeatureAdapter:
    """
    Adapter to convert Spark aggregated features to raw features.
    
    Training uses raw features (temperature, humidity, pressure, wind_speed, wind_direction).
    Inference receives aggregated features (temperature_mean, humidity_mean, etc.).
    This adapter maps aggregated -> raw for model compatibility.
    """
    
    def __init__(self):
        """Initialize feature adapter with mapping rules."""
        # Mapping from Spark aggregated features to raw features
        self.feature_mapping = {
            # Temperature: use mean as representative value
            'temperature': 'temperature_mean',
            'temperature_mean': 'temperature_mean',  # Already in right format
            
            # Humidity: use mean
            'humidity': 'humidity_mean',
            'humidity_mean': 'humidity_mean',
            
            # Pressure: use mean
            'sea_level_pressure': 'pressure_mean',
            'pressure': 'pressure_mean',
            'pressure_mean': 'pressure_mean',
            
            # Wind speed: use mean
            'wind_speed': 'wind_speed_mean',
            'wind_speed_mean': 'wind_speed_mean',
            
            # Wind direction: use mean
            'wind_direction': 'wind_direction_mean',
            'wind_direction_mean': 'wind_direction_mean',
            
            # Precipitation: use mean
            'precipitation': 'precipitation_mean',
            'precipitation_last_hour': 'precipitation_mean',
            'precipitation_mean': 'precipitation_mean',
        }
        
        # Default values if features are missing
        self.defaults = {
            'temperature': 20.0,  # °F
            'humidity': 50.0,      # %
            'sea_level_pressure': 1013.25,  # hPa
            'pressure': 1013.25,
            'wind_speed': 0.0,     # m/s
            'wind_direction': 0.0,  # degrees
            'precipitation': 0.0,  # mm
        }
    
    def adapt_features(self, spark_features: Dict) -> Dict:
        """
        Convert Spark aggregated features to raw features format.
        
        Args:
            spark_features: Dictionary with Spark aggregated features
                (temperature_mean, humidity_mean, pressure_mean, etc.)
        
        Returns:
            Dictionary with raw features (temperature, humidity, sea_level_pressure, etc.)
        """
        raw_features = {}
        
        # Map each raw feature from aggregated features
        for raw_feat, agg_feat in self.feature_mapping.items():
            if raw_feat == agg_feat:
                # Already in correct format, use directly
                value = spark_features.get(agg_feat, self.defaults.get(raw_feat, 0.0))
            else:
                # Map from aggregated to raw
                value = spark_features.get(agg_feat, self.defaults.get(raw_feat, 0.0))
            
            raw_features[raw_feat] = value
        
        # Also include additional aggregated features that might be useful
        # (std, min, max can provide additional context)
        for key in ['temperature_std', 'humidity_std', 'pressure_std', 
                   'wind_speed_std', 'temperature_min', 'temperature_max',
                   'humidity_min', 'humidity_max', 'pressure_min', 'pressure_max']:
            if key in spark_features:
                raw_features[key] = spark_features[key]
        
        # Preserve metadata
        for key in ['station_id', 'window_start', 'window_end', 'measurement_count']:
            if key in spark_features:
                raw_features[key] = spark_features[key]
        
        return raw_features
    
    def adapt_for_lstm(self, spark_features: Dict, lookback: int = 24) -> np.ndarray:
        """
        Convert Spark features to LSTM input format.
        
        Args:
            spark_features: Spark aggregated features
            lookback: Number of timesteps (for sequence models)
        
        Returns:
            Numpy array ready for LSTM input
        """
        raw_features = self.adapt_features(spark_features)
        
        # Extract features in the order expected by LSTM
        feature_list = [
            raw_features.get('temperature', self.defaults['temperature']),
            raw_features.get('humidity', self.defaults['humidity']),
            raw_features.get('sea_level_pressure', self.defaults['sea_level_pressure']),
            raw_features.get('wind_speed', self.defaults['wind_speed']),
            raw_features.get('wind_direction', self.defaults['wind_direction']),
        ]
        
        # For LSTM, we need a sequence. If we only have one aggregated window,
        # we repeat it for the lookback period (this is a limitation)
        # In practice, you'd want multiple aggregated windows for a proper sequence
        feature_array = np.array(feature_list)
        
        # Repeat for lookback timesteps (assuming same values across window)
        # This is a simplification - ideally you'd have multiple windows
        sequence = np.tile(feature_array, (lookback, 1))
        
        return sequence.reshape(1, lookback, -1)  # (1, lookback, features)
    
    def adapt_for_xgboost(self, spark_features: Dict) -> np.ndarray:
        """
        Convert Spark features to XGBoost input format.
        
        Args:
            spark_features: Spark aggregated features
        
        Returns:
            Numpy array ready for XGBoost input
        """
        raw_features = self.adapt_features(spark_features)
        
        # Extract features in order
        feature_list = [
            raw_features.get('temperature', self.defaults['temperature']),
            raw_features.get('humidity', self.defaults['humidity']),
            raw_features.get('sea_level_pressure', self.defaults['sea_level_pressure']),
            raw_features.get('wind_speed', self.defaults['wind_speed']),
            raw_features.get('wind_direction', self.defaults['wind_direction']),
            raw_features.get('precipitation', self.defaults['precipitation']),
        ]
        
        # Add aggregated statistics if available
        if 'temperature_std' in raw_features:
            feature_list.append(raw_features['temperature_std'])
        if 'humidity_std' in raw_features:
            feature_list.append(raw_features['humidity_std'])
        if 'pressure_std' in raw_features:
            feature_list.append(raw_features['pressure_std'])
        
        return np.array(feature_list).reshape(1, -1)


def create_feature_adapter() -> FeatureAdapter:
    """Create a feature adapter instance."""
    return FeatureAdapter()

