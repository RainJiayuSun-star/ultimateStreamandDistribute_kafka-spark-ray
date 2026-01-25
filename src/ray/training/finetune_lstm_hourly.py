"""
Fine-tune a pre-trained LSTM model on hourly data.
This script loads a model trained on daily data and fine-tunes it on hourly patterns.
"""

import os
import sys
import argparse
import logging
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.ray.training.data_loader import (
    load_hourly_normals,
    create_lstm_sequences,
    save_scaler
)
from src.ray.training.model_factory import configure_gpu
from src.ray.training.feature_adapter import FeatureAdapter
from src.ray.models.model_loader import MODEL_BASE_PATH

# Import TensorFlow/Keras at module level
try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    keras = None
    tf = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_pretrained_model(model_path: str):
    """
    Load a pre-trained LSTM model and its scalers.
    
    Args:
        model_path: Path to pre-trained model directory
    
    Returns:
        Tuple of (model, scaler_X, scaler_y, metadata)
    """
    model_path = Path(model_path)
    
    # Load metadata
    metadata_path = model_path / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Load model
    if keras is None:
        raise ImportError("TensorFlow is required for LSTM models")
    
    model_file = model_path / "model.h5"
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    
    try:
        model = keras.models.load_model(str(model_file))
    except (ValueError, TypeError) as e:
        logger.warning(f"Standard load failed, trying with compile=False: {e}")
        model = keras.models.load_model(str(model_file), compile=False)
        # Recompile with lower learning rate for fine-tuning
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.0001),  # Lower LR for fine-tuning
            loss='mse',
            metrics=['mae']
        )
    
    # Load scalers
    scaler_X_path = model_path / "scaler_X.pkl"
    scaler_y_path = model_path / "scaler_y.pkl"
    
    scaler_X = None
    scaler_y = None
    
    if scaler_X_path.exists():
        with open(scaler_X_path, 'rb') as f:
            scaler_X = pickle.load(f)
    if scaler_y_path.exists():
        with open(scaler_y_path, 'rb') as f:
            scaler_y = pickle.load(f)
    
    logger.info(f"Loaded pre-trained model from {model_path}")
    logger.info(f"Original model: {metadata.get('version', 'unknown')}")
    logger.info(f"Original features: {metadata.get('features', [])}")
    
    return model, scaler_X, scaler_y, metadata


def finetune_lstm_hourly(
    pretrained_model_path: str,
    hourly_data_path: str,
    lookback: int = 24,
    forecast_horizon: int = 24,
    epochs: int = 30,
    batch_size: int = 32,
    learning_rate: float = 0.0001,
    freeze_layers: bool = False,
    model_version: str = None,
    use_gpu: bool = True,
    gpu_id: int = 0,
    mixed_precision: bool = False
):
    """
    Fine-tune a pre-trained LSTM model on hourly data.
    
    Args:
        pretrained_model_path: Path to pre-trained model directory
        hourly_data_path: Path to hourly normals CSV
        lookback: Number of hours to look back (default: 24)
        forecast_horizon: Number of hours to predict ahead (default: 24)
        epochs: Number of fine-tuning epochs
        batch_size: Batch size for training
        learning_rate: Learning rate for fine-tuning (should be lower than initial training)
        freeze_layers: If True, freeze all layers except the last one
        model_version: Model version string
        use_gpu: Whether to use GPU
        gpu_id: GPU device ID
        mixed_precision: Enable mixed precision training
    """
    # Load pre-trained model
    logger.info(f"Loading pre-trained model from {pretrained_model_path}...")
    model, old_scaler_X, old_scaler_y, old_metadata = load_pretrained_model(pretrained_model_path)
    
    # Load hourly data
    logger.info(f"Loading hourly normals data from {hourly_data_path}...")
    data = load_hourly_normals(hourly_data_path)
    
    # Get original features from pre-trained model
    original_features = old_metadata.get('features', [])
    logger.info(f"Original model features: {original_features}")
    
    # Map hourly features to match original model features where possible
    # Original daily features: ['temperature', 'wind_avg', 'precipitation']
    # Hourly available: ['temperature', 'dewpoint', 'wind_speed', 'wind_direction', 'humidity']
    
    feature_mapping = {
        'temperature': 'temperature',  # Direct match
        'wind_avg': 'wind_speed',      # Use wind_speed as proxy for wind_avg
        'precipitation': None          # Not available in hourly normals
    }
    
    # Build feature list based on what's available
    features = []
    for orig_feat in original_features:
        if orig_feat in feature_mapping:
            mapped_feat = feature_mapping[orig_feat]
            if mapped_feat and mapped_feat in data.columns:
                features.append(mapped_feat)
            elif orig_feat in data.columns:
                features.append(orig_feat)  # Use original if available
        elif orig_feat in data.columns:
            features.append(orig_feat)  # Use original if available
    
    # If we don't have enough features, add available ones
    if len(features) < len(original_features):
        logger.warning(f"Feature count mismatch: original {len(original_features)}, available {len(features)}")
        logger.warning("This may require model adaptation. Using available features.")
        # Add additional hourly features if available
        additional_features = ['dewpoint', 'humidity', 'wind_direction']
        for feat in additional_features:
            if feat in data.columns and feat not in features:
                features.append(feat)
                if len(features) >= len(original_features):
                    break
    
    target = 'temperature'
    
    # Filter features to only those that exist
    features = [f for f in features if f in data.columns]
    
    if len(features) == 0:
        raise ValueError("No valid features found in hourly data")
    
    logger.info(f"Using features for fine-tuning: {features}")
    
    # Get original model's forecast_horizon from metadata BEFORE creating sequences
    original_forecast_horizon = old_metadata.get('forecast_horizon', 7)
    logger.info(f"Original model forecast_horizon: {original_forecast_horizon}")
    
    # Check if forecast_horizon matches - if not, use the original model's forecast_horizon
    if forecast_horizon != original_forecast_horizon:
        logger.warning(f"Forecast horizon mismatch: requested {forecast_horizon}, but model expects {original_forecast_horizon}")
        logger.warning(f"Using original model's forecast_horizon ({original_forecast_horizon}) for compatibility")
        forecast_horizon = original_forecast_horizon
    
    # Create sequences from hourly data
    logger.info("Creating LSTM sequences from hourly data...")
    X, y = create_lstm_sequences(
        data=data,
        lookback=lookback,
        forecast_horizon=forecast_horizon,
        features=features,
        target=target
    )
    
    logger.info(f"Created {len(X)} sequences: X shape {X.shape}, y shape {y.shape}")
    
    # Split data using time-series split (NO SHUFFLING)
    n_samples = len(X)
    train_end = int(n_samples * 0.7)
    val_end = int(n_samples * 0.85)
    
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
    logger.info(f"  Shapes - X_train: {X_train.shape}, y_train: {y_train.shape}")
    logger.info(f"  Shapes - X_val: {X_val.shape}, y_val: {y_val.shape}")
    
    # Check if model architecture matches
    expected_input_shape = (lookback, len(features))
    model_input_shape = model.input_shape[1:]  # Skip batch dimension
    model_output_shape = model.output_shape[1:]  # Get output shape (skip batch dimension)
    
    logger.info(f"Model architecture: input_shape={model_input_shape}, output_shape={model_output_shape}")
    
    # Validate that y shape matches model output shape
    if len(y_train.shape) > 1:
        actual_forecast_horizon = y_train.shape[1]
        if actual_forecast_horizon != original_forecast_horizon:
            logger.error(f"Output shape mismatch: y has {actual_forecast_horizon} timesteps, but model expects {original_forecast_horizon}")
            raise ValueError(f"Forecast horizon mismatch: y shape {y_train.shape} vs model output {model_output_shape}. The model was trained with forecast_horizon={original_forecast_horizon}, but sequences were created with forecast_horizon={forecast_horizon}")
    
    if model_input_shape != expected_input_shape:
        logger.warning(f"Model input shape mismatch!")
        logger.warning(f"  Model expects: {model_input_shape}")
        logger.warning(f"  Data provides: {expected_input_shape}")
        logger.warning("This may require model architecture changes or feature adaptation")
        
        # Try to adapt: if feature count differs, we may need a new input layer
        if model_input_shape[1] != len(features):
            logger.error(f"Cannot fine-tune: feature count mismatch ({model_input_shape[1]} vs {len(features)})")
            logger.error("Consider training a new model or adapting features")
            raise ValueError(f"Feature count mismatch: model expects {model_input_shape[1]} features, got {len(features)}")
        
        # If only lookback differs, adjust to match model
        if model_input_shape[0] != lookback:
            logger.warning(f"Lookback mismatch: model expects {model_input_shape[0]}, data uses {lookback}")
            logger.warning("Using model's expected lookback...")
            lookback = model_input_shape[0]
    
    # Recreate sequences with correct lookback and forecast_horizon
    if lookback != 24 or forecast_horizon != 24:  # Only recreate if different from default
        logger.info(f"Recreating sequences with lookback={lookback}, forecast_horizon={forecast_horizon}")
        X, y = create_lstm_sequences(
            data=data,
            lookback=lookback,
            forecast_horizon=forecast_horizon,
            features=features,
            target=target
        )
        logger.info(f"Recreated sequences: X shape {X.shape}, y shape {y.shape}")
        # Re-split with new data
        n_samples = len(X)
        train_end = int(n_samples * 0.7)
        val_end = int(n_samples * 0.85)
        logger.info(f"Re-splitting: n_samples={n_samples}, train_end={train_end}, val_end={val_end}")
        X_train = X[:train_end]
        y_train = y[:train_end]
        X_val = X[train_end:val_end]
        y_val = y[train_end:val_end]
        X_test = X[val_end:]
        y_test = y[val_end:]
        
        logger.info(f"Re-split after adjustment:")
        logger.info(f"  Train: {len(X_train)} samples, X shape: {X_train.shape}, y shape: {y_train.shape}")
        logger.info(f"  Val: {len(X_val)} samples, X shape: {X_val.shape}, y shape: {y_val.shape}")
        logger.info(f"  Test: {len(X_test)} samples, X shape: {X_test.shape}, y shape: {y_test.shape}")
        
        # Validate splits
        if len(X_val) == 0 or len(y_val) == 0:
            raise ValueError(f"Empty validation set after re-split: X_val={len(X_val)}, y_val={len(y_val)}, y_val shape={y_val.shape if hasattr(y_val, 'shape') else 'N/A'}")
    
    # Final validation: check output shape matches
    if len(y_train.shape) > 1:
        actual_forecast_horizon = y_train.shape[1]
        if actual_forecast_horizon != original_forecast_horizon:
            logger.error(f"Output shape mismatch: y has {actual_forecast_horizon} timesteps, but model expects {original_forecast_horizon}")
            raise ValueError(f"Forecast horizon mismatch: y shape {y_train.shape} vs model output {model_output_shape}")
    
    # Validate data before scaling
    if len(X_train) == 0 or len(y_train) == 0:
        raise ValueError(f"Empty training data: X_train={len(X_train)}, y_train={len(y_train)}")
    if len(X_val) == 0 or len(y_val) == 0:
        raise ValueError(f"Empty validation data: X_val={len(X_val)}, y_val={len(y_val)}, y_val shape={y_val.shape}")
    
    # Normalize data (create new scalers for hourly data)
    logger.info("Normalizing hourly data...")
    logger.info(f"Before scaling - X_train: {X_train.shape}, y_train: {y_train.shape}")
    logger.info(f"Before scaling - X_val: {X_val.shape}, y_val: {y_val.shape}")
    from sklearn.preprocessing import StandardScaler
    
    X_train_flat = X_train.reshape(-1, X_train.shape[-1])
    X_val_flat = X_val.reshape(-1, X_val.shape[-1])
    X_test_flat = X_test.reshape(-1, X_test.shape[-1])
    
    # Create new scalers for hourly data (different distribution than daily)
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    
    X_train_scaled = scaler_X.fit_transform(X_train_flat).reshape(X_train.shape)
    X_val_scaled = scaler_X.transform(X_val_flat).reshape(X_val.shape)
    X_test_scaled = scaler_X.transform(X_test_flat).reshape(X_test.shape)
    
    # Handle y scaling - ensure proper reshaping
    # y can be 1D (n_samples,) or 2D (n_samples, forecast_horizon)
    logger.info(f"Scaling y data - y_train shape: {y_train.shape}, y_val shape: {y_val.shape}")
    
    # Flatten y for scaling
    y_train_flat = y_train.flatten().reshape(-1, 1)
    y_val_flat = y_val.flatten().reshape(-1, 1)
    y_test_flat = y_test.flatten().reshape(-1, 1)
    
    # Validate flattened arrays
    if len(y_train_flat) == 0:
        raise ValueError(f"y_train_flat is empty after reshaping from shape {y_train.shape}")
    if len(y_val_flat) == 0:
        raise ValueError(f"y_val_flat is empty after reshaping from shape {y_val.shape}. Original y_val: {y_val}")
    
    y_train_scaled = scaler_y.fit_transform(y_train_flat)
    y_val_scaled = scaler_y.transform(y_val_flat)
    y_test_scaled = scaler_y.transform(y_test_flat)
    
    # Reshape back to original shape
    y_train_scaled = y_train_scaled.reshape(y_train.shape)
    y_val_scaled = y_val_scaled.reshape(y_val.shape)
    y_test_scaled = y_test_scaled.reshape(y_test.shape)
    
    # Configure GPU if requested
    if use_gpu:
        try:
            gpu_available = configure_gpu(gpu_id=gpu_id)
            if gpu_available:
                logger.info("GPU acceleration enabled")
                if mixed_precision:
                    try:
                        import tensorflow as tf
                        policy = tf.keras.mixed_precision.Policy('mixed_float16')
                        tf.keras.mixed_precision.set_global_policy(policy)
                        logger.info("Mixed precision training enabled (FP16)")
                    except Exception as e:
                        logger.warning(f"Could not enable mixed precision: {e}")
        except Exception as e:
            logger.warning(f"GPU configuration failed: {e}. Using CPU.")
    
    # Fine-tuning: optionally freeze layers
    if freeze_layers:
        logger.info("Freezing all layers except the last Dense layer for fine-tuning...")
        for layer in model.layers[:-1]:  # Freeze all except last layer
            layer.trainable = False
        logger.info(f"Frozen {len(model.layers) - 1} layers, {len(model.layers)} total layers")
    else:
        logger.info("Fine-tuning all layers (no freezing)")
        # Set lower learning rate for all layers
        for layer in model.layers:
            if hasattr(layer, 'kernel_initializer'):
                layer.trainable = True
    
    # Recompile with fine-tuning learning rate
    if keras is None:
        raise ImportError("TensorFlow is required for LSTM models")
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss='mse',
        metrics=['mae']
    )
    
    logger.info(f"Fine-tuning with learning rate: {learning_rate}")
    
    # Train (fine-tune) model
    logger.info("Fine-tuning model on hourly data...")
    try:
        from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
    except ImportError:
        EarlyStopping = None
        ModelCheckpoint = None
        ReduceLROnPlateau = None
    
    callbacks = []
    if EarlyStopping:
        callbacks.append(EarlyStopping(
            monitor='val_loss',
            patience=5,  # Lower patience for fine-tuning
            restore_best_weights=True,
            verbose=1
        ))
    if ReduceLROnPlateau:
        callbacks.append(ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=3,
            min_lr=1e-6,
            verbose=1
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
    logger.info("Evaluating fine-tuned model...")
    
    train_pred_scaled = model.predict(X_train_scaled, verbose=0)
    val_pred_scaled = model.predict(X_val_scaled, verbose=0)
    test_pred_scaled = model.predict(X_test_scaled, verbose=0)
    
    # Inverse transform predictions
    train_pred = scaler_y.inverse_transform(train_pred_scaled.reshape(-1, 1)).reshape(y_train.shape)
    val_pred = scaler_y.inverse_transform(val_pred_scaled.reshape(-1, 1)).reshape(y_val.shape)
    test_pred = scaler_y.inverse_transform(test_pred_scaled.reshape(-1, 1)).reshape(y_test.shape)
    
    # Inverse transform true values
    train_true = scaler_y.inverse_transform(y_train_scaled.reshape(-1, 1)).reshape(y_train.shape)
    val_true = scaler_y.inverse_transform(y_val_scaled.reshape(-1, 1)).reshape(y_val.shape)
    test_true = scaler_y.inverse_transform(y_test_scaled.reshape(-1, 1)).reshape(y_test.shape)
    
    # Calculate metrics (use first timestep for evaluation)
    def calculate_metrics(y_true, y_pred):
        # Take first timestep for 1-step ahead forecast
        if len(y_true.shape) > 1:
            y_true = y_true[:, 0]
            y_pred = y_pred[:, 0]
        
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        mask = np.abs(y_true) > 1e-6
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
    
    # Save fine-tuned model
    if model_version is None:
        model_version = f"LSTM_FineTuned_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    model_dir = Path(MODEL_BASE_PATH) / "forecasting" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving fine-tuned model to: {model_dir}")
    
    # Save model
    model_path = model_dir / "model.h5"
    model.save(str(model_path))
    logger.info(f"Saved model to {model_path}")
    
    # Save scalers
    save_scaler(scaler_X, str(model_dir / "scaler_X.pkl"))
    save_scaler(scaler_y, str(model_dir / "scaler_y.pkl"))
    
    # Save feature adapter
    feature_adapter = FeatureAdapter()
    adapter_path = model_dir / "feature_adapter.pkl"
    with open(adapter_path, 'wb') as f:
        pickle.dump(feature_adapter, f)
    logger.info(f"Saved feature adapter to {adapter_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'lstm_finetuned',
        'version': model_version,
        'training_date': datetime.now().isoformat(),
        'pretrained_model': str(pretrained_model_path),
        'pretrained_version': old_metadata.get('version', 'unknown'),
        'lookback': lookback,
        'forecast_horizon': forecast_horizon,
        'features': features,
        'target': target,
        'lstm_units': old_metadata.get('lstm_units', 64),
        'num_layers': old_metadata.get('num_layers', 2),
        'dropout_rate': old_metadata.get('dropout_rate', 0.2),
        'fine_tuning_epochs': epochs,
        'fine_tuning_learning_rate': learning_rate,
        'frozen_layers': freeze_layers,
        'train_metrics': train_metrics,
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'note': 'Fine-tuned on hourly data from pre-trained daily model. Trained on RAW features.'
    }
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")
    
    logger.info("Fine-tuning completed successfully!")
    logger.info(f"Fine-tuned model saved to: {model_dir}")
    return model, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune pre-trained LSTM model on hourly data")
    parser.add_argument("--pretrained-model", type=str, required=True,
                       help="Path to pre-trained model directory")
    parser.add_argument("--hourly-data", type=str, required=True,
                       help="Path to hourly normals CSV")
    parser.add_argument("--lookback", type=int, default=24,
                       help="Number of hours to look back (default: 24)")
    parser.add_argument("--forecast-horizon", type=int, default=24,
                       help="Number of hours to predict ahead (default: 24)")
    parser.add_argument("--epochs", type=int, default=30,
                       help="Number of fine-tuning epochs (default: 30)")
    parser.add_argument("--batch-size", type=int, default=32,
                       help="Batch size for training")
    parser.add_argument("--learning-rate", type=float, default=0.0001,
                       help="Learning rate for fine-tuning (default: 0.0001, lower than initial training)")
    parser.add_argument("--freeze-layers", action="store_true",
                       help="Freeze all layers except the last one (transfer learning)")
    parser.add_argument("--model-version", type=str,
                       help="Model version string")
    parser.add_argument("--use-gpu", action="store_true", default=True,
                       help="Use GPU for training")
    parser.add_argument("--no-gpu", dest="use_gpu", action="store_false",
                       help="Disable GPU and use CPU")
    parser.add_argument("--gpu-id", type=int, default=0,
                       help="GPU device ID to use (default: 0)")
    parser.add_argument("--mixed-precision", action="store_true",
                       help="Enable mixed precision training (FP16)")
    
    args = parser.parse_args()
    
    finetune_lstm_hourly(
        pretrained_model_path=args.pretrained_model,
        hourly_data_path=args.hourly_data,
        lookback=args.lookback,
        forecast_horizon=args.forecast_horizon,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        freeze_layers=args.freeze_layers,
        model_version=args.model_version,
        use_gpu=args.use_gpu,
        gpu_id=args.gpu_id,
        mixed_precision=args.mixed_precision
    )
