"""
Ray actor for performing ML inference on weather features.
Handles forecasting and anomaly detection.
"""

import logging
import ray
from typing import Dict, List, Optional, Any
try:
    from ray.models.forecasting_model import ForecastingModel
    from ray.models.anomaly_model import AnomalyModel
except ImportError:
    # Fallback for different import paths
    from models.forecasting_model import ForecastingModel
    from models.anomaly_model import AnomalyModel

logger = logging.getLogger(__name__)


@ray.remote
class InferenceActor:
    """
    Ray actor that performs ML inference on weather features.
    Models are loaded once when the actor is created.
    """
    
    def __init__(self, forecasting_model_path: Optional[str] = None, 
                 anomaly_model_path: Optional[str] = None):
        """
        Initialize inference actor and load models.
        
        Args:
            forecasting_model_path: Optional path to forecasting model
            anomaly_model_path: Optional path to anomaly model
        """
        logger.info("Initializing InferenceActor...")
        
        # Load models
        try:
            self.forecasting_model = ForecastingModel.from_disk(forecasting_model_path)
            logger.info("Forecasting model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading forecasting model: {e}")
            self.forecasting_model = ForecastingModel()  # Use simple model
        
        try:
            self.anomaly_model = AnomalyModel.from_disk(anomaly_model_path)
            logger.info("Anomaly model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading anomaly model: {e}")
            self.anomaly_model = AnomalyModel()  # Use simple model
        
        logger.info("InferenceActor initialized successfully")
    
    def predict(self, features: Dict) -> Dict:
        """
        Perform inference on weather features.
        
        Args:
            features: Dictionary with aggregated weather features from Spark
        
        Returns:
            Dictionary with predictions and anomaly detection results
        """
        try:
            # Get forecasting predictions
            forecast_result = self.forecasting_model.predict_temperature_trend(
                features, 
                horizon=24
            )
            
            # Get anomaly detection
            anomaly_details = self.anomaly_model.get_anomaly_details(features)
            
            # Format result
            result = {
                'station_id': features.get('station_id', 'UNKNOWN'),
                'window_start': features.get('window_start', ''),
                'window_end': features.get('window_end', ''),
                'forecast': {
                    'temperature_predictions': forecast_result['predictions'],
                    'upper_bound': forecast_result['upper_bound'],
                    'lower_bound': forecast_result['lower_bound'],
                    'horizon_hours': forecast_result['horizon_hours']
                },
                'anomaly': {
                    'score': anomaly_details['anomaly_score'],
                    'is_anomaly': anomaly_details['is_anomaly'],
                    'reasons': anomaly_details['reasons']
                },
                'current_conditions': {
                    'temperature_mean': features.get('temperature_mean'),
                    'humidity_mean': features.get('humidity_mean'),
                    'pressure_mean': features.get('pressure_mean'),
                    'wind_speed_mean': features.get('wind_speed_mean')
                }
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error in inference prediction: {e}")
            # Return error result
            return {
                'station_id': features.get('station_id', 'UNKNOWN'),
                'error': str(e),
                'forecast': None,
                'anomaly': None
            }
    
    def batch_predict(self, features_list: List[Dict]) -> List[Dict]:
        """
        Perform batch inference on multiple feature sets.
        
        Args:
            features_list: List of feature dictionaries
        
        Returns:
            List of prediction results
        """
        results = []
        for features in features_list:
            result = self.predict(features)
            results.append(result)
        
        return results
    
    def health_check(self) -> Dict:
        """
        Check if the actor is healthy and models are loaded.
        
        Returns:
            Dictionary with health status
        """
        return {
            'status': 'healthy',
            'forecasting_model_loaded': self.forecasting_model is not None,
            'anomaly_model_loaded': self.anomaly_model is not None,
            'forecasting_model_trained': self.forecasting_model.is_trained if self.forecasting_model else False,
            'anomaly_model_trained': self.anomaly_model.is_trained if self.anomaly_model else False
        }

