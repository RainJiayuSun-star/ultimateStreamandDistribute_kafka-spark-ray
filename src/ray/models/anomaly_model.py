"""
Anomaly detection model wrapper for weather data.
Supports simple threshold-based detection initially, can be upgraded to Isolation Forest/Autoencoder.
"""

import logging
import numpy as np
from typing import Dict, Optional, Any
from sklearn.ensemble import IsolationForest
try:
    from ray.models.model_loader import load_anomaly_model
except ImportError:
    # Fallback for different import paths
    from models.model_loader import load_anomaly_model

logger = logging.getLogger(__name__)


class AnomalyModel:
    """
    Wrapper class for anomaly detection model.
    Can use trained models or simple statistical thresholds.
    """
    
    def __init__(self, model: Optional[Any] = None):
        """
        Initialize anomaly detection model.
        
        Args:
            model: Pre-trained model object. If None, uses statistical thresholds.
        """
        self.model = model
        self.is_trained = model is not None
        
        # Default thresholds for simple statistical detection
        self.temperature_threshold_std = 3.0
        self.pressure_threshold_std = 3.0
        self.humidity_threshold_std = 3.0
    
    @classmethod
    def from_disk(cls, model_path: Optional[str] = None) -> 'AnomalyModel':
        """
        Load anomaly model from disk.
        
        Args:
            model_path: Optional path to model. If None, loads latest.
        
        Returns:
            AnomalyModel instance
        """
        model = load_anomaly_model(model_path)
        return cls(model=model)
    
    def preprocess_features(self, features: Dict) -> np.ndarray:
        """
        Preprocess features for model input.
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            Numpy array of features for model
        """
        feature_vector = [
            features.get('temperature_mean', 0.0),
            features.get('temperature_std', 0.0),
            features.get('humidity_mean', 0.0),
            features.get('pressure_mean', 1013.25),
            features.get('wind_speed_mean', 0.0),
            features.get('precipitation_mean', 0.0),
        ]
        
        return np.array(feature_vector).reshape(1, -1)
    
    def detect_anomaly(self, features: Dict) -> bool:
        """
        Detect if features represent an anomaly.
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            True if anomaly detected, False otherwise
        """
        anomaly_score = self.get_anomaly_score(features)
        # Threshold: score > 0.7 indicates anomaly
        return anomaly_score > 0.7
    
    def get_anomaly_score(self, features: Dict) -> float:
        """
        Get anomaly score (0-1, higher = more anomalous).
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            Anomaly score between 0 and 1
        """
        try:
            if self.is_trained and hasattr(self.model, 'predict'):
                # Use trained model (e.g., Isolation Forest)
                feature_vector = self.preprocess_features(features)
                prediction = self.model.predict(feature_vector)[0]
                
                # Isolation Forest returns -1 for anomaly, 1 for normal
                # Convert to score: -1 -> 1.0 (anomaly), 1 -> 0.0 (normal)
                if prediction == -1:
                    return 1.0
                else:
                    # Get decision function score if available
                    if hasattr(self.model, 'decision_function'):
                        score = self.model.decision_function(feature_vector)[0]
                        # Normalize to 0-1 (negative = anomaly)
                        return max(0.0, min(1.0, -score / 10.0))
                    return 0.0
            
            else:
                # Simple statistical threshold-based detection
                return self._statistical_anomaly_score(features)
        
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return 0.0
    
    def _statistical_anomaly_score(self, features: Dict) -> float:
        """
        Calculate anomaly score using statistical thresholds.
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            Anomaly score between 0 and 1
        """
        scores = []
        
        # Check temperature anomaly
        temp_mean = features.get('temperature_mean', 20.0)
        temp_std = features.get('temperature_std', 0.0)
        if temp_std > 0:
            # If temperature is far from mean (using std), it's anomalous
            temp_score = min(1.0, abs(temp_std) / (self.temperature_threshold_std * 2))
            scores.append(temp_score)
        
        # Check pressure anomaly
        pressure_mean = features.get('pressure_mean', 1013.25)
        pressure_std = features.get('pressure_std', 0.0)
        if pressure_std > 0:
            # Normal pressure range: 980-1040 hPa
            if pressure_mean < 980 or pressure_mean > 1040:
                scores.append(0.8)  # Extreme pressure
            else:
                pressure_score = min(1.0, abs(pressure_std) / (self.pressure_threshold_std * 2))
                scores.append(pressure_score)
        
        # Check humidity anomaly
        humidity_mean = features.get('humidity_mean', 50.0)
        humidity_std = features.get('humidity_std', 0.0)
        if humidity_std > 0:
            # Normal humidity: 0-100%
            if humidity_mean < 0 or humidity_mean > 100:
                scores.append(1.0)  # Invalid humidity
            else:
                humidity_score = min(1.0, abs(humidity_std) / (self.humidity_threshold_std * 2))
                scores.append(humidity_score)
        
        # Check for extreme precipitation
        precip_max = features.get('precipitation_max', 0.0)
        if precip_max > 50.0:  # Very high precipitation (mm)
            scores.append(0.9)
        
        # Return maximum score (if any feature is anomalous, flag it)
        if scores:
            return max(scores)
        return 0.0
    
    def get_anomaly_details(self, features: Dict) -> Dict:
        """
        Get detailed anomaly information.
        
        Args:
            features: Dictionary with aggregated weather features
        
        Returns:
            Dictionary with anomaly score, flag, and reasons
        """
        score = self.get_anomaly_score(features)
        is_anomaly = self.detect_anomaly(features)
        
        reasons = []
        if score > 0.7:
            # Identify which features are causing the anomaly
            temp_std = features.get('temperature_std', 0.0)
            pressure_mean = features.get('pressure_mean', 1013.25)
            humidity_mean = features.get('humidity_mean', 50.0)
            precip_max = features.get('precipitation_max', 0.0)
            
            if temp_std > self.temperature_threshold_std:
                reasons.append("High temperature variability")
            if pressure_mean < 980 or pressure_mean > 1040:
                reasons.append("Extreme pressure")
            if humidity_mean < 0 or humidity_mean > 100:
                reasons.append("Invalid humidity")
            if precip_max > 50.0:
                reasons.append("Extreme precipitation")
        
        return {
            'anomaly_score': round(score, 3),
            'is_anomaly': is_anomaly,
            'reasons': reasons if reasons else ["Normal conditions"]
        }

