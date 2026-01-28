"""
Training script for XGBoost forecasting model.
Trains on RAW historical data with feature engineering.
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.ray.training.data_loader import (
    load_daily_historical,
    prepare_xgboost_features,
    split_time_series
)
from src.ray.training.model_factory import create_xgboost_model
from src.ray.training.feature_adapter import FeatureAdapter
from src.ray.models.model_loader import save_model, MODEL_BASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_xgboost(
    daily_data_path: str,
    target: str = 'temp_max',
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    model_version: str = None
):
    """
    Train XGBoost model on RAW daily historical data.
    
    Args:
        daily_data_path: Path to daily historical CSV
        target: Target column name (temp_max, temp_min, or temp_avg)
        n_estimators: Number of boosting rounds
        max_depth: Maximum tree depth
        learning_rate: Learning rate
        subsample: Subsample ratio
        colsample_bytree: Column subsample ratio
        model_version: Model version string (e.g., 'v1.0')
    """
    # Load RAW data
    logger.info(f"Loading daily historical data (RAW features) from {daily_data_path}...")
    daily_data = load_daily_historical(daily_data_path)
    
    # Map target column names
    target_mapping = {
        'temp_max': 'temp_max',
        'temp_min': 'temp_min',
        'temp_avg': 'temp_avg',
        'temperature': 'temperature',
        'TMAX': 'temp_max',
        'TMIN': 'temp_min',
        'TAVG': 'temp_avg'
    }
    
    if target in target_mapping:
        target_col = target_mapping[target]
    else:
        target_col = target
    
    if target_col not in daily_data.columns:
        raise ValueError(f"Target column '{target_col}' not found in data. Available: {daily_data.columns.tolist()}")
    
    # Prepare features from RAW data
    logger.info("Preparing RAW features for XGBoost...")
    X, y = prepare_xgboost_features(
        data=daily_data,
        target_col=target_col
    )
    
    # Split data using time-series split (NO SHUFFLING)
    n_samples = len(X)
    train_end = int(n_samples * 0.7)
    val_end = int(n_samples * 0.85)
    
    X_train = X.iloc[:train_end]
    y_train = y.iloc[:train_end]
    X_val = X.iloc[train_end:val_end]
    y_val = y.iloc[train_end:val_end]
    X_test = X.iloc[val_end:]
    y_test = y.iloc[val_end:]
    
    logger.info(f"Time-series split (NO SHUFFLING):")
    logger.info(f"  Train: {len(X_train)} samples (70%)")
    logger.info(f"  Val: {len(X_val)} samples (15%)")
    logger.info(f"  Test: {len(X_test)} samples (15%)")
    logger.info(f"Features (RAW): {list(X.columns)}")
    
    # Create model
    logger.info("Creating XGBoost model...")
    model = create_xgboost_model(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree
    )
    
    # Train model
    logger.info("Training XGBoost model...")
    try:
        # Try new XGBoost 2.0+ API with callbacks
        from xgboost import callback
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[callback.EarlyStopping(rounds=10, save_best=True)],
            verbose=True
        )
    except (ImportError, AttributeError, TypeError):
        # Fallback to older XGBoost API (< 2.0)
        try:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=10,
                verbose=True
            )
        except TypeError:
            # If early_stopping_rounds doesn't work, train without it
            logger.warning("Early stopping not supported in this XGBoost version. Training without it.")
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=True
            )
    
    # Make predictions
    logger.info("Making predictions...")
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)
    test_pred = model.predict(X_test)
    
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
    
    train_metrics = calculate_metrics(y_train, train_pred)
    val_metrics = calculate_metrics(y_val, val_pred)
    test_metrics = calculate_metrics(y_test, test_pred)
    
    logger.info(f"Train Metrics - MAE: {train_metrics['mae']:.2f}, RMSE: {train_metrics['rmse']:.2f}, MAPE: {train_metrics['mape']:.2f}%")
    logger.info(f"Val Metrics - MAE: {val_metrics['mae']:.2f}, RMSE: {val_metrics['rmse']:.2f}, MAPE: {val_metrics['mape']:.2f}%")
    logger.info(f"Test Metrics - MAE: {test_metrics['mae']:.2f}, RMSE: {test_metrics['rmse']:.2f}, MAPE: {test_metrics['mape']:.2f}%")
    
    # Feature importance (convert numpy types to Python native types for JSON serialization)
    feature_importance = {k: float(v) for k, v in zip(X.columns, model.feature_importances_)}
    top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
    logger.info("Top 10 Features:")
    for feature, importance in top_features:
        logger.info(f"  {feature}: {importance:.4f}")
    
    # Save model
    if model_version is None:
        model_version = f"XGBoost_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    model_dir = Path(MODEL_BASE_PATH) / "forecasting" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving model to: {model_dir}")
    
    # Save XGBoost model
    import pickle
    model_path = model_dir / "model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    logger.info(f"Saved model to {model_path}")
    
    # Save feature adapter (for converting Spark aggregated features to raw features)
    feature_adapter = FeatureAdapter()
    adapter_path = model_dir / "feature_adapter.pkl"
    with open(adapter_path, 'wb') as f:
        pickle.dump(feature_adapter, f)
    logger.info(f"Saved feature adapter to {adapter_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'xgboost',
        'version': model_version,
        'training_date': datetime.now().isoformat(),
        'target': target_col,
        'n_estimators': n_estimators,
        'max_depth': max_depth,
        'learning_rate': learning_rate,
        'subsample': subsample,
        'colsample_bytree': colsample_bytree,
        'features': list(X.columns),  # RAW features used for training
        'feature_importance': feature_importance,
        'train_metrics': train_metrics,
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'note': 'Trained on RAW features. Use feature_adapter.pkl to convert Spark aggregated features at inference.'
    }
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")
    
    logger.info("XGBoost training completed successfully!")
    logger.info("NOTE: Model trained on RAW features. Feature adapter saved for inference on Spark-aggregated data.")
    return model, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train XGBoost forecasting model on RAW data")
    parser.add_argument("--daily-data", type=str, required=True, help="Path to daily historical CSV")
    parser.add_argument("--target", type=str, default="temp_max", help="Target column (temp_max, temp_min, temp_avg)")
    parser.add_argument("--n-estimators", type=int, default=100, help="Number of boosting rounds")
    parser.add_argument("--max-depth", type=int, default=6, help="Maximum tree depth")
    parser.add_argument("--learning-rate", type=float, default=0.1, help="Learning rate")
    parser.add_argument("--subsample", type=float, default=0.8, help="Subsample ratio")
    parser.add_argument("--colsample-bytree", type=float, default=0.8, help="Column subsample ratio")
    parser.add_argument("--model-version", type=str, help="Model version string")
    
    args = parser.parse_args()
    
    train_xgboost(
        daily_data_path=args.daily_data,
        target=args.target,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        model_version=args.model_version
    )

