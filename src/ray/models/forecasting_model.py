"""
Forecasting model wrapper for weather prediction.
Supports simple models initially, can be upgraded to LSTM/Prophet later.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from sklearn.linear_model import LinearRegression
try:
    from ray.models.model_loader import load_forecasting_model
except ImportError:
    # Fallback for different import paths
    from models.model_loader import load_forecasting_model

logger = logging.getLogger(__name__)


class ForecastingModel:
    """
    Wrapper class for weather forecasting model.
    Can use trained models or simple statistical models.
    """
    
    def __init__(self, model: Optional[Any] = None):
        """
        Initialize forecasting model.
        
        Args:
            model: Pre-trained model object. If None, creates a simple model.
        """
        self.model = model
        self.is_trained = model is not None
        
        if self.model is None:
            # Create a simple linear regression model as fallback
            logger.info("Using simple linear regression model for forecasting")
            self.model = LinearRegression()
            self.is_trained = False
            # For simple model, we'll use trend-based prediction
    
    @classmethod
    def from_disk(cls, model_path: Optional[str] = None) -> 'ForecastingModel':
        """
        Load forecasting model from disk.
        
        Args:
            model_path: Optional path to model. If None, loads latest.
        
        Returns:
            ForecastingModel instance
        """
        model = load_forecasting_model(model_path)
        return cls(model=model)
    
    def preprocess_features(self, features: Dict) -> np.ndarray:
        """
        Preprocess features for model input.
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            Numpy array of features for model
        """
        # Extract key features for forecasting
        feature_vector = [
            features.get('temperature_mean', 0.0),
            features.get('temperature_std', 0.0),
            features.get('humidity_mean', 0.0),
            features.get('pressure_mean', 1013.25),  # Default sea level pressure
            features.get('wind_speed_mean', 0.0),
            features.get('wind_direction_mean', 0.0),
            features.get('precipitation_mean', 0.0),
        ]
        
        return np.array(feature_vector).reshape(1, -1)
    
    def predict(self, features: Dict, horizon: int = 24) -> List[float]:
        """
        Predict weather for next N hours.
        
        Args:
            features: Dictionary with aggregated weather features
            horizon: Number of hours to predict (default: 24)
        
        Returns:
            List of predicted temperatures for next N hours
        """
        try:
            if self.is_trained and hasattr(self.model, 'predict'):
                # Use trained model
                feature_vector = self.preprocess_features(features)
                # For now, predict single value and extend it
                # In a real implementation, this would predict a sequence
                base_prediction = self.model.predict(feature_vector)[0]
                
                # Simple extension: assume gradual change
                predictions = [base_prediction] * horizon
                return predictions
            
            else:
                # Simple statistical model: use current mean with trend
                current_temp = features.get('temperature_mean', 20.0)
                temp_std = features.get('temperature_std', 0.0)
                
                # Simple trend: if std is high, assume variability
                # Otherwise, assume stable temperature
                if temp_std > 2.0:
                    # High variability - predict with some variation
                    trend = np.random.normal(0, temp_std * 0.1, horizon)
                    predictions = [current_temp + t for t in trend]
                else:
                    # Low variability - predict stable temperature
                    predictions = [current_temp] * horizon
                
                return predictions
        
        except Exception as e:
            logger.error(f"Error in forecasting prediction: {e}")
            # Fallback: return current temperature
            current_temp = features.get('temperature_mean', 20.0)
            return [current_temp] * horizon
    
    def predict_temperature_trend(self, features: Dict, horizon: int = 24) -> Dict:
        """
        Predict temperature trend with confidence intervals.
        
        Args:
            features: Dictionary with aggregated weather features
            horizon: Number of hours to predict
        
        Returns:
            Dictionary with predictions, upper bound, lower bound
        """
        predictions = self.predict(features, horizon)
        temp_std = features.get('temperature_std', 1.0)
        
        # Add confidence intervals (simple: ±2 std)
        upper_bound = [p + 2 * temp_std for p in predictions]
        lower_bound = [p - 2 * temp_std for p in predictions]
        
        return {
            'predictions': predictions,
            'upper_bound': upper_bound,
            'lower_bound': lower_bound,
            'horizon_hours': horizon
        }

