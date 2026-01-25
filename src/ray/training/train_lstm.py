"""
Training script for LSTM forecasting model.
Trains on RAW historical data (temperature, humidity, pressure, etc.)
and includes feature adapter for inference on Spark-aggregated data.
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.ray.training.data_loader import (
    load_hourly_normals,
    load_daily_historical,
    create_lstm_sequences,
    split_time_series,
    save_scaler
)
from src.ray.training.model_factory import create_lstm_model, configure_gpu
from src.ray.training.feature_adapter import FeatureAdapter
from src.ray.models.model_loader import save_model, MODEL_BASE_PATH
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_lstm(
    hourly_data_path: Optional[str] = None,
    daily_data_path: Optional[str] = None,
    lookback: int = 24,
    forecast_horizon: int = 24,
    epochs: int = 50,
    batch_size: int = 32,
    lstm_units: int = 64,
    num_layers: int = 2,
    dropout_rate: float = 0.2,
    model_version: str = None,
    use_gpu: bool = True,
    gpu_id: int = 0,
    mixed_precision: bool = False
):
    """
    Train LSTM model on RAW historical weather data.
    
    IMPORTANT: This trains on RAW features (temperature, humidity, pressure, etc.)
    but includes a feature adapter to convert Spark-aggregated features at inference.
    
    Args:
        hourly_data_path: Path to hourly normals CSV
        daily_data_path: Path to daily historical CSV
        lookback: Number of timesteps to look back
        forecast_horizon: Number of timesteps to predict
        epochs: Number of training epochs
        batch_size: Batch size for training
        lstm_units: Number of LSTM units
        num_layers: Number of LSTM layers
        dropout_rate: Dropout rate
        model_version: Model version string (e.g., 'v1.0')
        use_gpu: Whether to use GPU
        gpu_id: GPU device ID
        mixed_precision: Enable mixed precision training
    """
    # Load RAW data
    if hourly_data_path and os.path.exists(hourly_data_path):
        logger.info("Loading hourly normals data (RAW features)...")
        data = load_hourly_normals(hourly_data_path)
        # Use RAW features for training
        features = ['temperature', 'humidity', 'wind_speed', 'wind_direction']
        target = 'temperature'
        
    elif daily_data_path and os.path.exists(daily_data_path):
        logger.info("Loading daily historical data (RAW features)...")
        data = load_daily_historical(daily_data_path)
        # Use RAW features for training
        features = ['temperature', 'wind_avg', 'precipitation']
        target = 'temperature'
        
        # For daily data, adjust lookback and forecast
        lookback = min(lookback, 7)  # Max 7 days lookback
        forecast_horizon = min(forecast_horizon, 7)  # Max 7 days forecast
        
    else:
        raise ValueError("Must provide either hourly_data_path or daily_data_path")
    
    # Filter features to only those that exist
    features = [f for f in features if f in data.columns]
    
    if len(features) == 0:
        raise ValueError("No valid features found in data")
    
    logger.info(f"Training on RAW features: {features}")
    logger.info(f"Target variable: {target}")
    
    # Create sequences from RAW data
    logger.info("Creating LSTM sequences from RAW data...")
    X, y = create_lstm_sequences(
        data=data,
        lookback=lookback,
        forecast_horizon=forecast_horizon,
        features=features,
        target=target
    )
    
    # Split data using time-series split (NO SHUFFLING)
    # This is critical: we must preserve temporal order to avoid data leakage
    n_samples = len(X)
    train_end = int(n_samples * 0.7)  # 70% for training
    val_end = int(n_samples * 0.85)    # 15% for validation
    
    # Time-based split (earliest data -> train, middle -> val, latest -> test)
    X_train = X[:train_end]
    y_train = y[:train_end]
    X_val = X[train_end:val_end]
    y_val = y[train_end:val_end]
    X_test = X[val_end:]
    y_test = y[val_end:]
    
    logger.info(f"Time-series split (NO SHUFFLING):")
    logger.info(f"  Train: {len(X_train)} samples (70%)")
    logger.info(f"  Val: {len(X_val)} samples (15%)")
    logger.info(f"  Test: {len(X_test)} samples (15%)")
    
    # Normalize data
    logger.info("Normalizing data...")
    # Reshape for scaling
    X_train_flat = X_train.reshape(-1, X_train.shape[-1])
    X_val_flat = X_val.reshape(-1, X_val.shape[-1])
    X_test_flat = X_test.reshape(-1, X_test.shape[-1])
    
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    
    X_train_scaled = scaler_X.fit_transform(X_train_flat).reshape(X_train.shape)
    X_val_scaled = scaler_X.transform(X_val_flat).reshape(X_val.shape)
    X_test_scaled = scaler_X.transform(X_test_flat).reshape(X_test.shape)
    
    y_train_scaled = scaler_y.fit_transform(y_train.reshape(-1, 1)).reshape(y_train.shape)
    y_val_scaled = scaler_y.transform(y_val.reshape(-1, 1)).reshape(y_val.shape)
    y_test_scaled = scaler_y.transform(y_test.reshape(-1, 1)).reshape(y_test.shape)
    
    # Configure GPU if requested
    if use_gpu:
        try:
            gpu_available = configure_gpu(gpu_id=gpu_id)
            if gpu_available:
                logger.info("GPU acceleration enabled")
                # Enable mixed precision for faster training on RTX GPUs
                if mixed_precision:
                    try:
                        import tensorflow as tf
                        policy = tf.keras.mixed_precision.Policy('mixed_float16')
                        tf.keras.mixed_precision.set_global_policy(policy)
                        logger.info("Mixed precision training enabled (FP16)")
                    except Exception as e:
                        logger.warning(f"Could not enable mixed precision: {e}")
            else:
                logger.info("GPU not available, using CPU")
        except Exception as e:
            logger.warning(f"GPU configuration failed: {e}. Using CPU.")
    else:
        logger.info("GPU disabled, using CPU")
    
    # Create model
    logger.info("Creating LSTM model...")
    input_shape = (lookback, len(features))
    model = create_lstm_model(
        input_shape=input_shape,
        forecast_horizon=forecast_horizon,
        lstm_units=lstm_units,
        dropout_rate=dropout_rate,
        num_layers=num_layers,
        use_gpu=use_gpu
    )
    
    # Train model
    logger.info("Training LSTM model...")
    try:
        from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    except ImportError:
        EarlyStopping = None
        ModelCheckpoint = None
    
    callbacks = []
    if EarlyStopping:
        callbacks.append(EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        ))
    
    history = model.fit(
        X_train_scaled, y_train_scaled,
        validation_data=(X_val_scaled, y_val_scaled),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1
    )
    
    # Evaluate model
    logger.info("Evaluating model...")
    train_pred = model.predict(X_train_scaled, verbose=0)
    val_pred = model.predict(X_val_scaled, verbose=0)
    test_pred = model.predict(X_test_scaled, verbose=0)
    
    # Inverse transform predictions
    train_pred = scaler_y.inverse_transform(train_pred.reshape(-1, 1)).reshape(train_pred.shape)
    val_pred = scaler_y.inverse_transform(val_pred.reshape(-1, 1)).reshape(val_pred.shape)
    test_pred = scaler_y.inverse_transform(test_pred.reshape(-1, 1)).reshape(test_pred.shape)
    
    train_true = scaler_y.inverse_transform(y_train_scaled.reshape(-1, 1)).reshape(y_train.shape)
    val_true = scaler_y.inverse_transform(y_val_scaled.reshape(-1, 1)).reshape(y_val.shape)
    test_true = scaler_y.inverse_transform(y_test_scaled.reshape(-1, 1)).reshape(y_test.shape)
    
    # Calculate metrics
    def calculate_metrics(y_true, y_pred):
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        # MAPE calculation with better handling of small values
        # Avoid division by very small numbers
        mask = np.abs(y_true) > 1e-6  # Only calculate MAPE for non-zero values
        if mask.sum() > 0:
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        else:
            mape = 0.0
        return {'mae': float(mae), 'rmse': float(rmse), 'mape': float(mape)}
    
    train_metrics = calculate_metrics(train_true, train_pred)
    val_metrics = calculate_metrics(val_true, val_pred)
    test_metrics = calculate_metrics(test_true, test_pred)
    
    logger.info(f"Train Metrics - MAE: {train_metrics['mae']:.2f}, RMSE: {train_metrics['rmse']:.2f}, MAPE: {train_metrics['mape']:.2f}%")
    logger.info(f"Val Metrics - MAE: {val_metrics['mae']:.2f}, RMSE: {val_metrics['rmse']:.2f}, MAPE: {val_metrics['mape']:.2f}%")
    logger.info(f"Test Metrics - MAE: {test_metrics['mae']:.2f}, RMSE: {test_metrics['rmse']:.2f}, MAPE: {test_metrics['mape']:.2f}%")
    
    # Save model
    if model_version is None:
        model_version = f"LSTM_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    model_dir = Path(MODEL_BASE_PATH) / "forecasting" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving model to: {model_dir}")
    
    # Save Keras model
    model_path = model_dir / "model.h5"
    model.save(str(model_path))
    logger.info(f"Saved model to {model_path}")
    
    # Save scalers
    save_scaler(scaler_X, str(model_dir / "scaler_X.pkl"))
    save_scaler(scaler_y, str(model_dir / "scaler_y.pkl"))
    
    # Save feature adapter (for converting Spark aggregated features to raw features)
    import pickle
    feature_adapter = FeatureAdapter()
    adapter_path = model_dir / "feature_adapter.pkl"
    with open(adapter_path, 'wb') as f:
        pickle.dump(feature_adapter, f)
    logger.info(f"Saved feature adapter to {adapter_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'lstm',
        'version': model_version,
        'training_date': datetime.now().isoformat(),
        'lookback': lookback,
        'forecast_horizon': forecast_horizon,
        'features': features,  # RAW features used for training
        'target': target,
        'lstm_units': lstm_units,
        'num_layers': num_layers,
        'dropout_rate': dropout_rate,
        'epochs': epochs,
        'batch_size': batch_size,
        'train_metrics': train_metrics,
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'note': 'Trained on RAW features. Use feature_adapter.pkl to convert Spark aggregated features at inference.'
    }
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")
    
    logger.info("LSTM training completed successfully!")
    logger.info("NOTE: Model trained on RAW features. Feature adapter saved for inference on Spark-aggregated data.")
    return model, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LSTM forecasting model on RAW data")
    parser.add_argument("--hourly-data", type=str, help="Path to hourly normals CSV")
    parser.add_argument("--daily-data", type=str, help="Path to daily historical CSV")
    parser.add_argument("--lookback", type=int, default=24, help="Lookback window size")
    parser.add_argument("--forecast-horizon", type=int, default=24, help="Forecast horizon")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lstm-units", type=int, default=64, help="Number of LSTM units")
    parser.add_argument("--num-layers", type=int, default=2, help="Number of LSTM layers")
    parser.add_argument("--dropout-rate", type=float, default=0.2, help="Dropout rate")
    parser.add_argument("--model-version", type=str, help="Model version string")
    parser.add_argument("--use-gpu", action="store_true", default=True, help="Use GPU for training")
    parser.add_argument("--no-gpu", dest="use_gpu", action="store_false", help="Disable GPU and use CPU")
    parser.add_argument("--gpu-id", type=int, default=0, help="GPU device ID to use (default: 0)")
    parser.add_argument("--mixed-precision", action="store_true", help="Enable mixed precision training (FP16) for faster training on RTX GPUs")
    
    args = parser.parse_args()
    
    train_lstm(
        hourly_data_path=args.hourly_data,
        daily_data_path=args.daily_data,
        lookback=args.lookback,
        forecast_horizon=args.forecast_horizon,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lstm_units=args.lstm_units,
        num_layers=args.num_layers,
        dropout_rate=args.dropout_rate,
        model_version=args.model_version,
        use_gpu=args.use_gpu,
        gpu_id=args.gpu_id,
        mixed_precision=args.mixed_precision
    )

