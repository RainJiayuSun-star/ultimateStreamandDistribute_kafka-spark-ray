"""
Model factory for creating different types of forecasting models.
Supports LSTM, Prophet, and XGBoost models.
"""

import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def configure_gpu(gpu_memory_growth: bool = True, gpu_id: int = 0):
    """
    Configure TensorFlow to use GPU.
    
    Args:
        gpu_memory_growth: Enable memory growth to prevent OOM
        gpu_id: GPU device ID to use (0 for first GPU)
    
    Returns:
        True if GPU is available, False otherwise
    """
    try:
        import tensorflow as tf
        
        # Check if GPU is available
        gpus = tf.config.list_physical_devices('GPU')
        if len(gpus) == 0:
            logger.warning("No GPU devices found. Training will use CPU.")
            return False
        
        logger.info(f"Found {len(gpus)} GPU device(s)")
        
        # Configure GPU memory growth
        if gpu_memory_growth:
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                    logger.info(f"Enabled memory growth for GPU: {gpu.name}")
                except RuntimeError as e:
                    logger.warning(f"Could not set memory growth for {gpu.name}: {e}")
        
        # Set which GPU to use
        if gpu_id < len(gpus):
            tf.config.set_visible_devices(gpus[gpu_id], 'GPU')
            logger.info(f"Using GPU: {gpus[gpu_id].name}")
        else:
            logger.warning(f"GPU ID {gpu_id} not available. Using first GPU.")
            tf.config.set_visible_devices(gpus[0], 'GPU')
        
        # Log GPU info
        for i, gpu in enumerate(gpus):
            logger.info(f"GPU {i}: {gpu.name}")
            try:
                details = tf.config.experimental.get_device_details(gpu)
                logger.info(f"  Details: {details}")
            except:
                pass
        
        return True
        
    except ImportError:
        logger.warning("TensorFlow not available. Cannot configure GPU.")
        return False
    except Exception as e:
        logger.error(f"Error configuring GPU: {e}")
        return False


def create_lstm_model(
    input_shape: tuple,
    forecast_horizon: int = 24,
    lstm_units: int = 64,
    dropout_rate: float = 0.2,
    num_layers: int = 2,
    use_gpu: bool = True
):
    """
    Create an LSTM model for time series forecasting.
    
    Args:
        input_shape: Shape of input (timesteps, features)
        forecast_horizon: Number of timesteps to predict
        lstm_units: Number of LSTM units in each layer
        dropout_rate: Dropout rate for regularization
        num_layers: Number of LSTM layers
        use_gpu: Whether to configure and use GPU
    
    Returns:
        Compiled Keras model
    """
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        raise ImportError("TensorFlow is required for LSTM models. Install with: pip install tensorflow")
    
    # Log device placement (for debugging)
    logger.info(f"TensorFlow version: {tf.__version__}")
    try:
        logger.info(f"Built with CUDA: {tf.test.is_built_with_cuda()}")
        logger.info(f"GPU available: {len(tf.config.list_physical_devices('GPU')) > 0}")
    except:
        pass
    
    model = Sequential()
    
    # First LSTM layer
    model.add(LSTM(
        lstm_units,
        return_sequences=(num_layers > 1),
        input_shape=input_shape
    ))
    model.add(Dropout(dropout_rate))
    
    # Additional LSTM layers
    for i in range(1, num_layers):
        return_sequences = (i < num_layers - 1)
        model.add(LSTM(lstm_units, return_sequences=return_sequences))
        model.add(Dropout(dropout_rate))
    
    # Output layer
    model.add(Dense(forecast_horizon))
    
    # Compile model
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )
    
    logger.info(f"Created LSTM model with {num_layers} layers, {lstm_units} units")
    return model


def create_prophet_model(
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
    daily_seasonality: bool = False,
    seasonality_mode: str = 'multiplicative',
    changepoint_prior_scale: float = 0.05,
    holidays: Optional[pd.DataFrame] = None
):
    """
    Create a Prophet model for time series forecasting.
    
    Args:
        yearly_seasonality: Enable yearly seasonality
        weekly_seasonality: Enable weekly seasonality
        daily_seasonality: Enable daily seasonality
        seasonality_mode: 'additive' or 'multiplicative'
        changepoint_prior_scale: Flexibility of trend changes
        holidays: DataFrame with holidays (optional)
    
    Returns:
        Prophet model instance
    """
    try:
        from prophet import Prophet
    except ImportError:
        raise ImportError("Prophet is required. Install with: pip install prophet")
    
    model = Prophet(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=daily_seasonality,
        seasonality_mode=seasonality_mode,
        changepoint_prior_scale=changepoint_prior_scale
    )
    
    if holidays is not None:
        model.add_country_holidays(country_name='US')
    
    logger.info("Created Prophet model")
    return model


def create_xgboost_model(
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    min_child_weight: int = 1,
    reg_alpha: float = 0.0,
    reg_lambda: float = 1.0,
    random_state: int = 42
):
    """
    Create an XGBoost model for time series forecasting.
    
    Args:
        n_estimators: Number of boosting rounds
        max_depth: Maximum tree depth
        learning_rate: Learning rate
        subsample: Subsample ratio of training instances
        colsample_bytree: Subsample ratio of columns
        min_child_weight: Minimum sum of instance weight in child (regularization)
        reg_alpha: L1 regularization term
        reg_lambda: L2 regularization term
        random_state: Random seed
    
    Returns:
        XGBoost model instance
    """
    try:
        import xgboost as xgb
    except ImportError:
        raise ImportError("XGBoost is required. Install with: pip install xgboost")
    
    model = xgb.XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda,
        random_state=random_state,
        objective='reg:squarederror'
    )
    
    logger.info(f"Created XGBoost model with {n_estimators} estimators, max_depth={max_depth}")
    return model


def create_model(model_type: str, **kwargs) -> Any:
    """
    Factory function to create a model by type.
    
    Args:
        model_type: 'lstm', 'prophet', or 'xgboost'
        **kwargs: Model-specific parameters
    
    Returns:
        Model instance
    """
    model_type = model_type.lower()
    
    if model_type == 'lstm':
        return create_lstm_model(**kwargs)
    elif model_type == 'prophet':
        return create_prophet_model(**kwargs)
    elif model_type == 'xgboost':
        return create_xgboost_model(**kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}. Choose from: lstm, prophet, xgboost")

