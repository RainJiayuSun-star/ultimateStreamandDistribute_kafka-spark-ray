"""
Improved XGBoost training script with enhanced features and hyperparameters.
This demonstrates the improvements recommended in IMPROVING_MODEL_PERFORMANCE.md
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
    split_time_series
)
from src.ray.training.model_factory import create_xgboost_model
from src.ray.training.feature_adapter import FeatureAdapter
from src.ray.models.model_loader import save_model, MODEL_BASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def prepare_enhanced_features(
    data: pd.DataFrame,
    target_col: str = 'temp_max',
    lookback_days: int = 30
) -> tuple:
    """
    Prepare enhanced features for XGBoost with more lag features,
    rolling statistics, and seasonal features.
    
    Args:
        data: DataFrame with time series data
        target_col: Name of target column
        lookback_days: Maximum days to look back
    
    Returns:
        Tuple of (X, y) where X is features DataFrame and y is target Series
    """
    df = data.copy()
    
    # Ensure sorted by date
    if 'DATE' in df.columns:
        df = df.sort_values('DATE').reset_index(drop=True)
        df['date'] = pd.to_datetime(df['DATE'])
    else:
        raise ValueError("DATE column not found")
    
    # Extract time features
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['day_of_year'] = df['date'].dt.dayofyear
    df['day_of_week'] = df['date'].dt.dayofweek
    df['week_of_year'] = df['date'].dt.isocalendar().week
    
    # 1. Extended lag features
    if target_col in df.columns:
        for lag in [1, 2, 3, 5, 7, 14, 21, 30]:
            if lag <= lookback_days:
                df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
    
    # 2. Multiple rolling windows
    if target_col in df.columns:
        for window in [3, 7, 14, 30]:
            if window <= len(df):
                df[f'{target_col}_rolling_mean_{window}'] = df[target_col].rolling(window=window, min_periods=1).mean()
                df[f'{target_col}_rolling_std_{window}'] = df[target_col].rolling(window=window, min_periods=1).std()
                df[f'{target_col}_rolling_min_{window}'] = df[target_col].rolling(window=window, min_periods=1).min()
                df[f'{target_col}_rolling_max_{window}'] = df[target_col].rolling(window=window, min_periods=1).max()
    
    # 3. Seasonal features (sin/cos encoding)
    df['sin_month'] = np.sin(2 * np.pi * df['month'] / 12)
    df['cos_month'] = np.cos(2 * np.pi * df['month'] / 12)
    df['sin_day_of_year'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
    df['cos_day_of_year'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)
    df['sin_week_of_year'] = np.sin(2 * np.pi * df['week_of_year'] / 52)
    df['cos_week_of_year'] = np.cos(2 * np.pi * df['week_of_year'] / 52)
    
    # 4. Interaction features
    if 'temp_max' in df.columns and 'temp_min' in df.columns:
        df['temp_range'] = df['temp_max'] - df['temp_min']
        df['temp_avg'] = (df['temp_max'] + df['temp_min']) / 2
    
    if 'precipitation' in df.columns:
        df['precipitation_binary'] = (df['precipitation'] > 0).astype(int)
        df['precipitation_log'] = np.log1p(df['precipitation'])  # log(1+x) to handle zeros
    
    # 5. Weather regime features
    df['is_winter'] = df['month'].isin([12, 1, 2]).astype(int)
    df['is_summer'] = df['month'].isin([6, 7, 8]).astype(int)
    df['is_spring'] = df['month'].isin([3, 4, 5]).astype(int)
    df['is_fall'] = df['month'].isin([9, 10, 11]).astype(int)
    
    # 6. Cross-feature interactions
    if 'wind_avg' in df.columns and 'temperature' in df.columns:
        df['wind_temp_interaction'] = df['wind_avg'] * df['temperature']
    
    if 'precipitation' in df.columns and 'temperature' in df.columns:
        df['precip_temp_interaction'] = df['precipitation'] * df['temperature']
    
    # 7. Rate of change features
    if target_col in df.columns:
        df[f'{target_col}_diff_1'] = df[target_col].diff(1)
        df[f'{target_col}_diff_7'] = df[target_col].diff(7)
        df[f'{target_col}_pct_change_7'] = df[target_col].pct_change(7)
    
    # Select features (exclude date columns and target)
    feature_cols = [col for col in df.columns 
                   if col not in ['DATE', 'date', target_col, 'STATION', 'NAME', 
                                 'LATITUDE', 'LONGITUDE', 'ELEVATION']]
    
    # Remove columns with too many missing values
    missing_threshold = 0.5
    feature_cols = [col for col in feature_cols 
                   if df[col].isna().sum() / len(df) < missing_threshold]
    
    X = df[feature_cols].copy()
    y = df[target_col].copy()
    
    # Remove rows with missing target
    mask = ~y.isna()
    X = X[mask]
    y = y[mask]
    
    # Fill remaining NaN with forward fill, then backward fill, then median
    X = X.ffill().bfill()
    X = X.fillna(X.median())
    
    logger.info(f"Prepared {len(X)} samples with {len(X.columns)} enhanced features")
    logger.info(f"Features: {list(X.columns)}")
    
    return X, y


def train_xgboost_improved(
    daily_data_path: str,
    target: str = 'temp_max',
    n_estimators: int = 200,  # Increased from 100
    max_depth: int = 5,  # Slightly reduced from 6
    learning_rate: float = 0.05,  # Reduced from 0.1
    subsample: float = 0.85,
    colsample_bytree: float = 0.85,
    min_child_weight: int = 3,  # NEW: regularization
    reg_alpha: float = 0.1,  # NEW: L1 regularization
    reg_lambda: float = 1.0,  # NEW: L2 regularization
    model_version: str = None
):
    """
    Train improved XGBoost model with enhanced features and hyperparameters.
    
    Args:
        daily_data_path: Path to daily historical CSV
        target: Target column name
        n_estimators: Number of boosting rounds (increased)
        max_depth: Maximum tree depth (slightly reduced)
        learning_rate: Learning rate (reduced for stability)
        subsample: Subsample ratio
        colsample_bytree: Column subsample ratio
        min_child_weight: Minimum sum of instance weight in child (regularization)
        reg_alpha: L1 regularization
        reg_lambda: L2 regularization
        model_version: Model version string
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
    
    # Prepare enhanced features
    logger.info("Preparing enhanced features for XGBoost...")
    X, y = prepare_enhanced_features(
        data=daily_data,
        target_col=target_col,
        lookback_days=30
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
    logger.info(f"Enhanced features: {len(X.columns)} total")
    
    # Create improved model
    logger.info("Creating improved XGBoost model...")
    model = create_xgboost_model(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda
    )
    
    # Train model
    logger.info("Training improved XGBoost model...")
    try:
        from xgboost import callback
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[callback.EarlyStopping(rounds=20, save_best=True)],
            verbose=True
        )
    except (ImportError, AttributeError, TypeError):
        try:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=20,
                verbose=True
            )
        except TypeError:
            logger.warning("Early stopping not supported. Training without it.")
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
        mask = np.abs(y_true) > 1e-6
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
    
    # Feature importance
    feature_importance = {k: float(v) for k, v in zip(X.columns, model.feature_importances_)}
    top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:15]
    logger.info("Top 15 Features:")
    for feature, importance in top_features:
        logger.info(f"  {feature}: {importance:.4f}")
    
    # Save model
    if model_version is None:
        model_version = f"XGBoost_Improved_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    model_dir = Path(MODEL_BASE_PATH) / "forecasting" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving model to: {model_dir}")
    
    # Save XGBoost model
    import pickle
    model_path = model_dir / "model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    logger.info(f"Saved model to {model_path}")
    
    # Save feature adapter
    feature_adapter = FeatureAdapter()
    adapter_path = model_dir / "feature_adapter.pkl"
    with open(adapter_path, 'wb') as f:
        pickle.dump(feature_adapter, f)
    logger.info(f"Saved feature adapter to {adapter_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'xgboost_improved',
        'version': model_version,
        'training_date': datetime.now().isoformat(),
        'target': target_col,
        'hyperparameters': {
            'n_estimators': n_estimators,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'min_child_weight': min_child_weight,
            'reg_alpha': reg_alpha,
            'reg_lambda': reg_lambda
        },
        'features': list(X.columns),
        'feature_importance': feature_importance,
        'train_metrics': train_metrics,
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'note': 'Improved XGBoost with enhanced features and hyperparameters'
    }
    
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")
    
    logger.info("Improved XGBoost training completed successfully!")
    return model, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train improved XGBoost model")
    parser.add_argument("--daily-data", type=str, required=True, help="Path to daily historical CSV")
    parser.add_argument("--target", type=str, default="temp_max", help="Target column")
    parser.add_argument("--n-estimators", type=int, default=200, help="Number of boosting rounds")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum tree depth")
    parser.add_argument("--learning-rate", type=float, default=0.05, help="Learning rate")
    parser.add_argument("--subsample", type=float, default=0.85, help="Subsample ratio")
    parser.add_argument("--colsample-bytree", type=float, default=0.85, help="Column subsample ratio")
    parser.add_argument("--min-child-weight", type=int, default=3, help="Min child weight")
    parser.add_argument("--reg-alpha", type=float, default=0.1, help="L1 regularization")
    parser.add_argument("--reg-lambda", type=float, default=1.0, help="L2 regularization")
    parser.add_argument("--model-version", type=str, help="Model version string")
    
    args = parser.parse_args()
    
    train_xgboost_improved(
        daily_data_path=args.daily_data,
        target=args.target,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        min_child_weight=args.min_child_weight,
        reg_alpha=args.reg_alpha,
        reg_lambda=args.reg_lambda,
        model_version=args.model_version
    )

