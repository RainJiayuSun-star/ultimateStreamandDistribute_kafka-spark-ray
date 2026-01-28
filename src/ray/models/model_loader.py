"""
Model loading utilities for Ray inference.
Loads trained LSTM models and their dependencies (scalers, feature adapters).
"""

import os
import json
import pickle
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import numpy as np

# Don't import TensorFlow/Keras at module level - it creates non-serializable KerasLazyLoader objects
# Import them inside functions that need them instead (like use_finetuned_lstm.py does)
# This prevents Ray serialization issues when the module is loaded via importlib

logger = logging.getLogger(__name__)

# Model storage path (mounted volume in Docker)
MODEL_BASE_PATH = os.getenv("MODEL_STORAGE_PATH", "/app/models")
FORECASTING_MODEL_DIR = "trained/forecasting"
LSTM_MODEL_NAME = "LSTM_FineTuned_20260124_193541"


def get_model_path(model_name: str = LSTM_MODEL_NAME) -> Path:
    """
    Get the full path to a model directory.
    
    Args:
        model_name: Name of the model directory
    
    Returns:
        Path to model directory
    """
    return Path(MODEL_BASE_PATH) / FORECASTING_MODEL_DIR / model_name


def load_metadata(model_path: Path) -> Dict[str, Any]:
    """
    Load model metadata from JSON file.
    
    Args:
        model_path: Path to model directory
    
    Returns:
        Dictionary with model metadata
    
    Raises:
        FileNotFoundError: If metadata file doesn't exist
    """
    metadata_path = model_path / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    logger.info(f"Loaded metadata for model: {metadata.get('version', 'unknown')}")
    return metadata


def load_lstm_model(model_path: Path) -> Any:
    """
    Load LSTM model from H5 file.
    
    Args:
        model_path: Path to model directory
    
    Returns:
        Loaded Keras model
    
    Raises:
        ImportError: If TensorFlow/Keras is not available
        FileNotFoundError: If model file doesn't exist
    """
    # Import TensorFlow/Keras inside the function to avoid serialization issues
    # This matches the pattern used in use_finetuned_lstm.py
    try:
        import tensorflow as tf
        from tensorflow import keras
    except ImportError:
        raise ImportError("TensorFlow/Keras is required for LSTM models")
    
    model_file = model_path / "model.h5"
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    
    try:
        logger.info(f"Loading LSTM model from {model_file}")
        model = keras.models.load_model(str(model_file))
        logger.info("Model loaded successfully")
    except (ValueError, TypeError) as e:
        logger.warning(f"Standard load failed, trying with compile=False: {e}")
        try:
            model = keras.models.load_model(str(model_file), compile=False)
            # Recompile for inference
            model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=0.001),
                loss='mse',
                metrics=['mae']
            )
            logger.info("Model loaded and recompiled successfully")
        except (ValueError, TypeError) as e2:
            # Handle Keras version compatibility issue
            # The error is about InputLayer config with 'batch_shape' and 'optional' parameters
            if "batch_shape" in str(e2) or "optional" in str(e2) or "Unrecognized keyword arguments" in str(e2):
                logger.warning(f"Keras version compatibility issue detected: {e2}")
                logger.info("Model was saved with a version that uses 'batch_shape'/'optional', but current Keras doesn't support them")
                logger.info("Attempting to load model using custom_objects to handle InputLayer compatibility...")
                
                try:
                    # Create a custom InputLayer class that handles compatibility
                    from tensorflow.keras.layers import InputLayer as OriginalInputLayer
                    
                    class CompatibleInputLayer(OriginalInputLayer):
                        """InputLayer that handles 'batch_shape' and 'optional' for cross-version compatibility."""
                        @classmethod
                        def from_config(cls, config):
                            # Remove unsupported parameters
                            config = config.copy()
                            config.pop('optional', None)  # Remove 'optional' if present
                            
                            # Convert batch_shape to input_shape (Keras 3.x doesn't support batch_shape)
                            if 'batch_shape' in config:
                                batch_shape = config.pop('batch_shape')
                                if batch_shape and batch_shape[0] is None:
                                    # Remove batch dimension to get input_shape
                                    if len(batch_shape) > 1:
                                        config['input_shape'] = tuple(batch_shape[1:])
                                    elif len(batch_shape) == 1:
                                        # If only batch dimension, set empty input_shape
                                        config['input_shape'] = ()
                            
                            # Call parent with cleaned config
                            return super().from_config(config)
                    
                    # Handle DTypePolicy compatibility (Keras 2.x to 3.x)
                    # Keras 3.x uses different dtype policy serialization
                    # Also need to handle quantization_config which Keras 3.x doesn't support
                    from tensorflow.keras.layers import Dense as OriginalDense, LSTM as OriginalLSTM, Dropout as OriginalDropout
                    
                    def create_compatible_layer(original_layer_class, layer_name):
                        """Create a compatibility wrapper that strips quantization_config."""
                        class CompatibleLayer(original_layer_class):
                            """Layer that strips quantization_config for Keras 3.x compatibility."""
                            @classmethod
                            def from_config(cls, config):
                                # Remove quantization_config if present (not supported in Keras 3.x)
                                config = config.copy()
                                config.pop('quantization_config', None)
                                # Call parent with cleaned config
                                return super().from_config(config)
                        CompatibleLayer.__name__ = f"Compatible{layer_name}"
                        return CompatibleLayer
                    
                    CompatibleDense = create_compatible_layer(OriginalDense, 'Dense')
                    CompatibleLSTM = create_compatible_layer(OriginalLSTM, 'LSTM')
                    CompatibleDropout = create_compatible_layer(OriginalDropout, 'Dropout')
                    
                    custom_objects = {
                        'InputLayer': CompatibleInputLayer,
                        'Dense': CompatibleDense,
                        'LSTM': CompatibleLSTM,
                        'Dropout': CompatibleDropout
                    }
                    
                    # Add DTypePolicy compatibility
                    # Keras 3.x changed how DTypePolicy is serialized
                    # We need to provide a custom deserializer
                    try:
                        from keras.mixed_precision import dtype_policy
                        
                        # Create a compatibility class for DTypePolicy
                        # This allows Keras to deserialize old DTypePolicy objects
                        class CompatibleDTypePolicy:
                            """Compatibility wrapper for DTypePolicy deserialization."""
                            def __init__(self, name='float32'):
                                self.name = name
                                self._policy = dtype_policy(name)
                            
                            @classmethod
                            def from_config(cls, config):
                                """Deserialize from config."""
                                if isinstance(config, str):
                                    return cls(config)
                                elif isinstance(config, dict):
                                    name = config.get('name', 'float32')
                                    return cls(name)
                                else:
                                    return cls('float32')
                            
                            def __getattr__(self, name):
                                # Delegate to the actual policy
                                return getattr(self._policy, name)
                        
                        custom_objects['DTypePolicy'] = CompatibleDTypePolicy
                        logger.info("Registered CompatibleDTypePolicy for backward compatibility")
                    except (ImportError, AttributeError) as dtype_error:
                        logger.warning(f"Could not set up DTypePolicy compatibility: {dtype_error}")
                        # Create a proper DTypePolicy stub with all required attributes
                        import numpy as np
                        import tensorflow as tf
                        
                        class MinimalDTypePolicy:
                            """Proper DTypePolicy stub with all required attributes."""
                            def __init__(self, name='float32'):
                                self.name = name
                                self._name = name
                                # Convert string dtype name to actual dtype
                                # Handle common dtype names
                                dtype_map = {
                                    'float32': tf.float32,
                                    'float64': tf.float64,
                                    'float16': tf.float16,
                                    'int32': tf.int32,
                                    'int64': tf.int64,
                                    'mixed_float16': tf.float16,  # Default to float16 for mixed
                                }
                                tf_dtype = dtype_map.get(name, tf.float32)
                                # Keras 3.x expects these attributes
                                self.compute_dtype = tf_dtype
                                self.variable_dtype = tf_dtype
                            
                            @classmethod
                            def from_config(cls, config):
                                if isinstance(config, str):
                                    return cls(config)
                                elif isinstance(config, dict):
                                    name = config.get('name', 'float32')
                                    return cls(name)
                                return cls('float32')
                            
                            def __repr__(self):
                                return f"MinimalDTypePolicy(name='{self.name}')"
                            
                            def get_config(self):
                                return {'name': self.name}
                            
                            # Delegate any other attribute access to avoid AttributeError
                            def __getattr__(self, name):
                                # Return None for unknown attributes to avoid errors
                                # Some Keras code might check for these
                                if name in ['name', '_name']:
                                    return getattr(self, name)
                                return None
                        
                        custom_objects['DTypePolicy'] = MinimalDTypePolicy
                        logger.warning("Using MinimalDTypePolicy stub with required attributes")
                    
                    # Try loading with custom_objects and safe_mode=False
                    # safe_mode=False allows loading models with custom objects that might not match exactly
                    try:
                        model = keras.models.load_model(
                            str(model_file),
                            compile=False,
                            custom_objects=custom_objects,
                            safe_mode=False  # Disable safe mode for compatibility
                        )
                        logger.info("Model loaded successfully with CompatibleInputLayer and safe_mode=False")
                    except Exception as safe_mode_error:
                        # If safe_mode=False doesn't work, try with legacy loading
                        logger.warning(f"safe_mode=False failed: {safe_mode_error}")
                        logger.info("Trying legacy model loading approach...")
                        
                        # Use tf.keras.models.load_model which might have better backward compatibility
                        model = tf.keras.models.load_model(
                            str(model_file),
                            compile=False,
                            custom_objects=custom_objects
                        )
                        logger.info("Model loaded successfully using tf.keras.models.load_model")
                    
                    # Recompile for inference
                    model.compile(
                        optimizer=keras.optimizers.Adam(learning_rate=0.001),
                        loss='mse',
                        metrics=['mae']
                    )
                    logger.info("Model loaded and recompiled successfully")
                except Exception as e3:
                    logger.error(f"Custom InputLayer approach also failed: {e3}")
                    raise ValueError(
                        f"Failed to load model due to Keras version incompatibility. "
                        f"The model was saved with a version that uses 'batch_shape'/'optional' parameters, "
                        f"but the current Keras version doesn't support them. "
                        f"\n\nOriginal error: {e2}\n"
                        f"Custom layer error: {e3}"
                    ) from e3
            else:
                # Re-raise if it's a different error
                logger.error(f"Failed to load model: {e2}")
                raise ValueError(
                    f"Failed to load LSTM model from {model_file}. "
                    f"This may be due to version incompatibility or corrupted model file. "
                    f"Error: {e2}"
                ) from e2
    
    return model


def load_scalers(model_path: Path) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Load feature and target scalers.
    
    Args:
        model_path: Path to model directory
    
    Returns:
        Tuple of (scaler_X, scaler_y)
    """
    scaler_X_path = model_path / "scaler_X.pkl"
    scaler_y_path = model_path / "scaler_y.pkl"
    
    scaler_X = None
    scaler_y = None
    
    # Custom unpickler to handle numpy version compatibility
    # numpy 2.x uses numpy._core, but numpy 1.x uses numpy.core
    class CompatibleUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            # Redirect numpy._core to numpy.core for compatibility
            if module.startswith('numpy._core'):
                module = module.replace('numpy._core', 'numpy.core')
            elif module == 'numpy._core':
                module = 'numpy.core'
            return super().find_class(module, name)
    
    if scaler_X_path.exists():
        try:
            with open(scaler_X_path, 'rb') as f:
                scaler_X = pickle.load(f)
            logger.info("Loaded feature scaler (scaler_X)")
        except (ModuleNotFoundError, AttributeError) as e:
            if 'numpy._core' in str(e):
                logger.warning(f"Retrying with compatibility unpickler: {e}")
                with open(scaler_X_path, 'rb') as f:
                    unpickler = CompatibleUnpickler(f)
                    scaler_X = unpickler.load()
                logger.info("Loaded feature scaler (scaler_X) with compatibility mode")
            else:
                raise
    else:
        logger.warning(f"Feature scaler not found: {scaler_X_path}")
    
    if scaler_y_path.exists():
        try:
            with open(scaler_y_path, 'rb') as f:
                scaler_y = pickle.load(f)
            logger.info("Loaded target scaler (scaler_y)")
        except (ModuleNotFoundError, AttributeError) as e:
            if 'numpy._core' in str(e):
                logger.warning(f"Retrying with compatibility unpickler: {e}")
                with open(scaler_y_path, 'rb') as f:
                    unpickler = CompatibleUnpickler(f)
                    scaler_y = unpickler.load()
                logger.info("Loaded target scaler (scaler_y) with compatibility mode")
            else:
                raise
    else:
        logger.warning(f"Target scaler not found: {scaler_y_path}")
    
    return scaler_X, scaler_y


def load_feature_adapter(model_path: Path) -> Optional[Any]:
    """
    Load feature adapter for converting Spark features to model input.
    
    Args:
        model_path: Path to model directory
    
    Returns:
        FeatureAdapter instance or None
    """
    adapter_path = model_path / "feature_adapter.pkl"
    
    if adapter_path.exists():
        with open(adapter_path, 'rb') as f:
            adapter = pickle.load(f)
        logger.info("Loaded feature adapter")
        return adapter
    else:
        logger.warning(f"Feature adapter not found: {adapter_path}")
        # Try to import and create default adapter
        try:
            # Try different import paths
            try:
                from ray.training.feature_adapter import FeatureAdapter
            except ImportError:
                # Try with src prefix (support both Docker and local)
                import sys
                if os.path.exists('/app/src'):
                    sys.path.insert(0, '/app/src')
                else:
                    # Local environment
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                    src_path = os.path.join(project_root, 'src')
                    sys.path.insert(0, src_path)
                from ray.training.feature_adapter import FeatureAdapter
            
            logger.info("Creating default feature adapter")
            return FeatureAdapter()
        except ImportError as e:
            logger.warning(f"Could not create feature adapter: {e} - will use raw features")
            return None


def load_forecasting_model(model_name: str = LSTM_MODEL_NAME) -> Dict[str, Any]:
    """
    Load complete forecasting model with all dependencies.
    
    Args:
        model_name: Name of the model directory
    
    Returns:
        Dictionary with keys:
            - 'model': Keras model
            - 'scaler_X': Feature scaler
            - 'scaler_y': Target scaler
            - 'metadata': Model metadata
            - 'model_path': Path to model directory
    
    Raises:
        FileNotFoundError: If model directory doesn't exist
        ImportError: If required libraries are missing
    """
    model_path = get_model_path(model_name)
    
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model directory not found: {model_path}\n"
            f"Expected path: {model_path.absolute()}"
        )
    
    logger.info(f"Loading forecasting model from: {model_path}")
    
    # Load all components
    metadata = load_metadata(model_path)
    model = load_lstm_model(model_path)
    scaler_X, scaler_y = load_scalers(model_path)
    # FeatureAdapter no longer needed - we calculate features directly from Spark output
    
    logger.info(f"Successfully loaded model: {metadata.get('version', model_name)}")
    logger.info(f"Model type: {metadata.get('model_type', 'unknown')}")
    logger.info(f"Lookback: {metadata.get('lookback', 'unknown')}")
    logger.info(f"Forecast horizon: {metadata.get('forecast_horizon', 'unknown')}")
    
    return {
        'model': model,
        'scaler_X': scaler_X,
        'scaler_y': scaler_y,
        'metadata': metadata,
        'model_path': model_path
    }


def validate_model_loaded(model_dict: Dict[str, Any]) -> bool:
    """
    Validate that a loaded model has all required components.
    
    Args:
        model_dict: Dictionary returned by load_forecasting_model
    
    Returns:
        True if model is valid, False otherwise
    """
    required_keys = ['model', 'metadata']
    missing_keys = [key for key in required_keys if key not in model_dict]
    
    if missing_keys:
        logger.error(f"Model missing required components: {missing_keys}")
        return False
    
    if model_dict['model'] is None:
        logger.error("Model is None")
        return False
    
    logger.info("Model validation passed")
    return True

