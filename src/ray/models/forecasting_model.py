"""
Forecasting model wrapper for LSTM temperature predictions.
Handles feature adaptation, scaling, and prediction formatting.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ForecastingModel:
    """
    Wrapper for LSTM forecasting model.
    Handles feature preprocessing, model inference, and result formatting.
    """
    
    def __init__(
        self,
        model: Any,
        scaler_X: Optional[Any],
        scaler_y: Optional[Any],
        metadata: Dict[str, Any],
        feature_adapter: Optional[Any] = None  # Kept for backward compatibility, not used
    ):
        """
        Initialize forecasting model wrapper.
        
        Args:
            model: Loaded Keras LSTM model
            scaler_X: Feature scaler (StandardScaler)
            scaler_y: Target scaler (StandardScaler)
            metadata: Model metadata dictionary
            feature_adapter: Deprecated - kept for backward compatibility only
        """
        self.model = model
        self.scaler_X = scaler_X
        self.scaler_y = scaler_y
        self.metadata = metadata
        
        # Extract model parameters from metadata
        self.lookback = metadata.get('lookback', 24)
        self.forecast_horizon = metadata.get('forecast_horizon', 24)
        self.features = metadata.get('features', ['temperature', 'humidity', 'wind_speed'])
        self.target = metadata.get('target', 'temperature')
        
        logger.info(f"ForecastingModel initialized:")
        logger.info(f"  Lookback: {self.lookback}")
        logger.info(f"  Forecast horizon: {self.forecast_horizon}")
        logger.info(f"  Features: {self.features}")
        logger.info(f"  Target: {self.target}")
    
    def preprocess_features(self, spark_features: Dict[str, Any]) -> np.ndarray:
        """
        Preprocess Spark aggregated features for model input.
        
        Args:
            spark_features: Dictionary with Spark aggregated features
                (temperature_mean, humidity_mean, wind_speed_mean, etc.)
        
        Returns:
            Preprocessed numpy array ready for model input
        """
        # Extract the 3 features the model needs: temperature, wind_speed, dewpoint
        # IMPORTANT: All values must be in METRIC units (Celsius, m/s) to match training data
        # Spark outputs: temperature_mean, humidity_mean, wind_speed_mean
        # Temperature should be in Celsius (not Fahrenheit)
        temperature = spark_features.get('temperature_mean', spark_features.get('temperature', 20.0))  # Celsius
        wind_speed = spark_features.get('wind_speed_mean', spark_features.get('wind_speed', 0.0))  # m/s
        humidity = spark_features.get('humidity_mean', spark_features.get('humidity', 50.0))  # percentage
        
        # Calculate dewpoint from temperature and humidity (both in Celsius)
        # Simplified Magnus formula: Td = T - ((100 - RH) / 5)
        # This formula works when T and Td are in Celsius
        dewpoint = temperature - ((100 - humidity) / 5)
        
        # Create features dict with the 3 features in the order expected by model
        model_features = {
            'temperature': temperature,
            'wind_speed': wind_speed,
            'dewpoint': dewpoint
        }
        
        # Create sequence from these 3 features
        sequence = self._create_sequence_from_features(model_features)
        
        # Scale features if scaler is available
        if self.scaler_X:
            # Reshape for scaler: (1, lookback, features) -> (lookback, features)
            original_shape = sequence.shape
            flattened = sequence.reshape(-1, sequence.shape[-1])
            scaled = self.scaler_X.transform(flattened)
            sequence = scaled.reshape(original_shape)
        
        return sequence
    
    def _create_sequence_from_features(self, features: Dict[str, Any]) -> np.ndarray:
        """
        Create LSTM input sequence from feature dictionary.
        Repeats the current features for lookback timesteps.
        
        Args:
            features: Dictionary with feature values
        
        Returns:
            Numpy array of shape (1, lookback, num_features)
        """
        # Extract features in order expected by model
        feature_values = []
        defaults = {
            'temperature': 20.0,  # Celsius (metric) - matches model training
            'humidity': 50.0,  # percentage
            'sea_level_pressure': 1013.25,  # hPa
            'pressure': 1013.25,  # hPa
            'wind_speed': 0.0,  # m/s (metric) - matches model training
            'wind_direction': 0.0,  # degrees
            'dewpoint': 10.0  # Celsius (metric)
        }
        
        # Try to get features in the order specified in metadata
        for feat in self.features:
            # Try various key names
            value = None
            for key in [feat, f"{feat}_mean", f"{feat}_avg"]:
                if key in features:
                    value = features[key]
                    break
            
            if value is None:
                value = defaults.get(feat, 0.0)
                logger.warning(f"Feature {feat} not found, using default: {value}")
            
            feature_values.append(float(value))
        
        # Create sequence by repeating features for lookback period
        feature_array = np.array(feature_values)
        sequence = np.tile(feature_array, (self.lookback, 1))
        
        # Reshape to (1, lookback, features) for model input
        return sequence.reshape(1, self.lookback, -1)
    
    def _run_model_once(self, model_input: np.ndarray) -> List[float]:
        """Run model on (1, lookback, features), inverse transform, return list of temps."""
        pred = self.model.predict(model_input, verbose=0)
        if self.scaler_y:
            orig_shape = pred.shape
            flat = pred.reshape(-1, 1)
            pred = self.scaler_y.inverse_transform(flat)
            pred = pred.reshape(orig_shape)
        if pred.ndim == 3:
            return pred[0, :, 0].tolist()
        return pred[0, :].tolist()
    
    def predict(
        self,
        features: Dict[str, Any],
        horizon: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate temperature forecast predictions.
        
        Args:
            features: Dictionary with Spark aggregated features
            horizon: Number of hours to predict (defaults to model's forecast_horizon)
        
        Returns:
            Dictionary with predictions:
                - 'temperature_predictions': List of predicted temperatures
                - 'horizon_hours': Number of hours predicted
                - 'confidence': Confidence scores (if available)
        """
        if horizon is None:
            horizon = self.forecast_horizon
        
        # Recursive 24h is disabled: chaining 7h runs causes unrealistic jumps (e.g. -12°C → 43°C)
        # because we feed synthetic "history" (our predictions + constant wind/dewpoint) that
        # doesn't match training, and errors compound. Use single forward pass only.
        if horizon > self.forecast_horizon:
            logger.warning(
                f"Requested horizon {horizon}h exceeds model forecast_horizon {self.forecast_horizon}h. "
                "Capping at model horizon (recursive 24h disabled to avoid drift)."
            )
            horizon = self.forecast_horizon
        
        try:
            model_input = self.preprocess_features(features)
            temperature_predictions = self._run_model_once(model_input)
            temperature_predictions = temperature_predictions[:horizon]
            
            logger.info(f"Generated {len(temperature_predictions)} predictions")
            return {
                'temperature_predictions': temperature_predictions,
                'horizon_hours': len(temperature_predictions),
                'confidence': None
            }
        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            raise
    
    def predict_short_term(
        self,
        features: Dict[str, Any],
        hours: int = 12
    ) -> Dict[str, Any]:
        """
        Generate short-term predictions (6-12 hours).
        
        Args:
            features: Dictionary with Spark aggregated features
            hours: Number of hours to predict (default: 12)
        
        Returns:
            Dictionary with short-term predictions
        """
        return self.predict(features, horizon=hours)
    
    def predict_long_term(
        self,
        features: Dict[str, Any],
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate long-term predictions (24+ hours).
        
        Args:
            features: Dictionary with Spark aggregated features
            hours: Number of hours to predict (default: 24)
        
        Returns:
            Dictionary with long-term predictions
        """
        return self.predict(features, horizon=hours)

