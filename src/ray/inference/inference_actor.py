"""
Ray actor for ML inference.
Loads models once and handles inference requests.
CPU-only mode (GPU disabled).
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List
import numpy as np

# CRITICAL: Import Ray package BEFORE adding local ray module to path
# Temporarily remove /app/src from path to ensure we import the installed Ray package
original_path = sys.path[:]
src_path_to_remove = None

if os.path.exists('/app/src'):
    # Docker environment
    if '/app/src' in sys.path:
        sys.path.remove('/app/src')
        src_path_to_remove = '/app/src'
else:
    # Local environment - find and temporarily remove src path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    src_path = os.path.join(project_root, 'src')
    if src_path in sys.path:
        sys.path.remove(src_path)
        src_path_to_remove = src_path

# Now import Ray package (will find installed package, not local directory)
import ray

# Restore src path and add it back for local module imports
if src_path_to_remove:
    sys.path.insert(0, src_path_to_remove)
elif os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    src_path = os.path.join(project_root, 'src')
    sys.path.insert(0, src_path)

# Don't import model_loader at module level - it contains TensorFlow/Keras imports
# that create non-serializable KerasLazyLoader objects. We'll import it inside
# __init__ instead to avoid Ray serialization issues.
import importlib.util

# Store paths for later use in __init__
def _get_models_dir():
    """Get the path to the models directory."""
    if os.path.exists('/app/src'):
        return '/app/src/ray/models'
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        return os.path.join(project_root, 'src', 'ray', 'models')

# Try to import TensorFlow (this is OK at module level)
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    tf = None

logger = logging.getLogger(__name__)


@ray.remote  # CPU-only: no GPU allocation
class InferenceActor:
    """
    Ray actor for performing ML inference.
    Loads models once on initialization and handles inference requests.
    """
    
    def __init__(
        self,
        model_name: str = "LSTM_FineTuned_20260124_193541",
        use_gpu: bool = False,
        gpu_id: int = 0
    ):
        """
        Initialize inference actor and load models.
        
        Args:
            model_name: Name of the model directory to load
            use_gpu: Whether to use GPU for inference
            gpu_id: GPU device ID to use
        """
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.gpu_id = gpu_id
        self.forecasting_model = None
        self.model_loaded = False
        
        logger.info(f"InferenceActor initializing with model: {model_name}")
        
        # Configure GPU if available (disabled by default - CPU-only mode)
        if use_gpu and TENSORFLOW_AVAILABLE:
            self._configure_gpu()
        else:
            logger.info("Running in CPU-only mode (GPU disabled)")
        
        # Load models
        try:
            self._load_models()
            logger.info("InferenceActor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize InferenceActor: {e}")
            raise
    
    def _configure_gpu(self):
        """Configure TensorFlow to use GPU."""
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available, GPU configuration skipped")
            return
        
        try:
            gpus = tf.config.list_physical_devices('GPU')
            if len(gpus) == 0:
                logger.warning("No GPU devices found, using CPU")
                self.use_gpu = False
                return
            
            logger.info(f"Found {len(gpus)} GPU device(s)")
            
            # Configure GPU memory growth to prevent OOM
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                    logger.info(f"Enabled memory growth for GPU: {gpu.name}")
                except RuntimeError as e:
                    logger.warning(f"Could not set memory growth: {e}")
            
            # Set visible GPU device
            if self.gpu_id < len(gpus):
                tf.config.set_visible_devices(gpus[self.gpu_id], 'GPU')
                logger.info(f"Using GPU: {gpus[self.gpu_id].name}")
            else:
                logger.warning(f"GPU ID {self.gpu_id} not available, using first GPU")
                tf.config.set_visible_devices(gpus[0], 'GPU')
                
        except Exception as e:
            logger.warning(f"GPU configuration failed: {e}, falling back to CPU")
            self.use_gpu = False
    
    def _load_models(self):
        """Load forecasting model and dependencies."""
        # Import model_loader here to avoid serialization issues
        # This ensures TensorFlow/Keras imports happen on the worker, not during class definition
        models_dir = _get_models_dir()
        
        # Load model_loader module
        _model_loader_file = os.path.join(models_dir, 'model_loader.py')
        _model_loader_spec = importlib.util.spec_from_file_location("ray.models.model_loader", _model_loader_file)
        _model_loader_module = importlib.util.module_from_spec(_model_loader_spec)
        _model_loader_spec.loader.exec_module(_model_loader_module)
        load_forecasting_model = _model_loader_module.load_forecasting_model
        validate_model_loaded = _model_loader_module.validate_model_loaded
        
        # Load forecasting_model module
        _forecasting_model_file = os.path.join(models_dir, 'forecasting_model.py')
        _forecasting_model_spec = importlib.util.spec_from_file_location("ray.models.forecasting_model", _forecasting_model_file)
        _forecasting_model_module = importlib.util.module_from_spec(_forecasting_model_spec)
        _forecasting_model_spec.loader.exec_module(_forecasting_model_module)
        ForecastingModel = _forecasting_model_module.ForecastingModel
        
        try:
            logger.info(f"Loading model: {self.model_name}")
            model_dict = load_forecasting_model(self.model_name)
            
            if not validate_model_loaded(model_dict):
                raise ValueError("Model validation failed")
            
            # Create forecasting model wrapper
            # FeatureAdapter is no longer needed - we calculate features directly from Spark output
            self.forecasting_model = ForecastingModel(
                model=model_dict['model'],
                scaler_X=model_dict['scaler_X'],
                scaler_y=model_dict['scaler_y'],
                metadata=model_dict['metadata']
            )
            
            self.model_loaded = True
            logger.info("Models loaded successfully")
            
        except FileNotFoundError as e:
            logger.error(f"Model files not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise
    
    def predict(
        self,
        features: Dict[str, Any],
        horizon: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform forecasting inference.
        
        Args:
            features: Dictionary with Spark aggregated features
            horizon: Number of hours to predict (None = use model default)
        
        Returns:
            Dictionary with predictions:
                - 'forecast': Dictionary with temperature_predictions, horizon_hours
                - 'horizon_hours': Number of hours predicted
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded")
        
        try:
            # Generate predictions
            if horizon:
                predictions = self.forecasting_model.predict(features, horizon=horizon)
            else:
                predictions = self.forecasting_model.predict(features)
            
            return {
                'forecast': predictions,
                'horizon_hours': predictions.get('horizon_hours', 24)
            }
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise
    
    def predict_short_term(self, features: Dict[str, Any], hours: int = 12) -> Dict[str, Any]:
        """
        Generate short-term predictions (6-12 hours).
        
        Args:
            features: Dictionary with Spark aggregated features
            hours: Number of hours to predict
        
        Returns:
            Dictionary with short-term predictions
        """
        return self.predict(features, horizon=hours)
    
    def predict_long_term(self, features: Dict[str, Any], hours: int = 24) -> Dict[str, Any]:
        """
        Generate long-term predictions (24+ hours).
        
        Args:
            features: Dictionary with Spark aggregated features
            hours: Number of hours to predict
        
        Returns:
            Dictionary with long-term predictions
        """
        return self.predict(features, horizon=hours)
    
    def batch_predict(
        self,
        features_list: List[Dict[str, Any]],
        horizon: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform batch inference on multiple feature sets.
        
        Args:
            features_list: List of feature dictionaries
            horizon: Number of hours to predict
        
        Returns:
            List of prediction dictionaries
        """
        results = []
        for features in features_list:
            try:
                result = self.predict(features, horizon=horizon)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch prediction failed for one item: {e}")
                results.append({'error': str(e)})
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check actor health and model status.
        
        Returns:
            Dictionary with health status
        """
        return {
            'status': 'healthy' if self.model_loaded else 'unhealthy',
            'model_loaded': self.model_loaded,
            'model_name': self.model_name,
            'use_gpu': self.use_gpu,
            'gpu_id': self.gpu_id
        }
