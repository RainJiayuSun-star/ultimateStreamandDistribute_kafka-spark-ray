"""
Training script for Prophet forecasting model.
Trains on RAW historical data for long-term seasonal forecasting.
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
    prepare_prophet_data,
    split_time_series
)
from src.ray.training.model_factory import create_prophet_model
from src.ray.models.model_loader import save_model, MODEL_BASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_prophet(
    daily_data_path: str,
    target: str = 'temp_max',
    forecast_days: int = 365,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
    seasonality_mode: str = 'multiplicative',
    changepoint_prior_scale: float = 0.05,
    model_version: str = None
):
    """
    Train Prophet model on RAW daily historical data.
    
    Args:
        daily_data_path: Path to daily historical CSV
        target: Target column name (temp_max, temp_min, or temp_avg)
        forecast_days: Number of days to forecast ahead
        yearly_seasonality: Enable yearly seasonality
        weekly_seasonality: Enable weekly seasonality
        seasonality_mode: 'additive' or 'multiplicative'
        changepoint_prior_scale: Flexibility of trend changes
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
    
    # Prepare Prophet data
    logger.info("Preparing data for Prophet...")
    prophet_data = prepare_prophet_data(
        data=daily_data,
        date_col='DATE',
        target_col=target_col
    )
    
    # Split data using time-series split (NO SHUFFLING)
    train_data, val_data, test_data = split_time_series(
        prophet_data,
        train_ratio=0.8,
        val_ratio=0.1,
        test_ratio=0.1,
        date_col='ds'
    )
    
    logger.info(f"Time-series split: Train={len(train_data)}, Val={len(val_data)}, Test={len(test_data)}")
    
    # Create model
    logger.info("Creating Prophet model...")
    model = create_prophet_model(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=False,  # Daily data doesn't need daily seasonality
        seasonality_mode=seasonality_mode,
        changepoint_prior_scale=changepoint_prior_scale
    )
    
    # Train model
    logger.info("Training Prophet model...")
    model.fit(train_data)
    
    # Make predictions for train, validation and test sets
    logger.info("Making predictions...")
    
    # Training predictions (for completeness)
    train_future = model.make_future_dataframe(periods=0)  # No future periods, just historical
    train_forecast = model.predict(train_future)
    train_pred = train_forecast.head(len(train_data))['yhat'].values
    train_true = train_data['y'].values
    
    # Validation predictions
    val_future = model.make_future_dataframe(periods=len(val_data))
    val_forecast = model.predict(val_future)
    val_pred = val_forecast.tail(len(val_data))['yhat'].values
    val_true = val_data['y'].values
    
    # Test predictions
    test_future = model.make_future_dataframe(periods=len(test_data))
    test_forecast = model.predict(test_future)
    test_pred = test_forecast.tail(len(test_data))['yhat'].values
    test_true = test_data['y'].values
    
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
    
    # Retrain on full dataset for final model
    # Prophet can only be fit once, so create a new model instance
    logger.info("Retraining on full dataset...")
    final_model = create_prophet_model(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=False,
        seasonality_mode=seasonality_mode,
        changepoint_prior_scale=changepoint_prior_scale
    )
    final_model.fit(prophet_data)
    model = final_model  # Use the final model for saving
    
    # Save model
    if model_version is None:
        model_version = f"Prophet_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    model_dir = Path(MODEL_BASE_PATH) / "forecasting" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving model to: {model_dir}")
    
    # Save Prophet model (using pickle)
    import pickle
    model_path = model_dir / "model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    logger.info(f"Saved model to {model_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'prophet',
        'version': model_version,
        'training_date': datetime.now().isoformat(),
        'target': target_col,
        'forecast_days': forecast_days,
        'yearly_seasonality': yearly_seasonality,
        'weekly_seasonality': weekly_seasonality,
        'seasonality_mode': seasonality_mode,
        'changepoint_prior_scale': changepoint_prior_scale,
        'train_metrics': train_metrics,
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'training_samples': len(prophet_data)
    }
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")
    
    # Make future forecast
    future = model.make_future_dataframe(periods=forecast_days)
    forecast = model.predict(future)
    
    # Save forecast
    forecast_path = model_dir / "forecast.csv"
    forecast.to_csv(forecast_path, index=False)
    logger.info(f"Saved forecast to {forecast_path}")
    
    logger.info("Prophet training completed successfully!")
    return model, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Prophet forecasting model on RAW data")
    parser.add_argument("--daily-data", type=str, required=True, help="Path to daily historical CSV")
    parser.add_argument("--target", type=str, default="temp_max", help="Target column (temp_max, temp_min, temp_avg)")
    parser.add_argument("--forecast-days", type=int, default=365, help="Number of days to forecast")
    parser.add_argument("--yearly-seasonality", action="store_true", default=True, help="Enable yearly seasonality")
    parser.add_argument("--no-yearly-seasonality", dest="yearly_seasonality", action="store_false")
    parser.add_argument("--weekly-seasonality", action="store_true", default=True, help="Enable weekly seasonality")
    parser.add_argument("--no-weekly-seasonality", dest="weekly_seasonality", action="store_false")
    parser.add_argument("--seasonality-mode", type=str, default="multiplicative", choices=["additive", "multiplicative"])
    parser.add_argument("--changepoint-prior-scale", type=float, default=0.05, help="Changepoint prior scale")
    parser.add_argument("--model-version", type=str, help="Model version string")
    
    args = parser.parse_args()
    
    train_prophet(
        daily_data_path=args.daily_data,
        target=args.target,
        forecast_days=args.forecast_days,
        yearly_seasonality=args.yearly_seasonality,
        weekly_seasonality=args.weekly_seasonality,
        seasonality_mode=args.seasonality_mode,
        changepoint_prior_scale=args.changepoint_prior_scale,
        model_version=args.model_version
    )

