"""
Data loading and preprocessing utilities for model training.
Handles loading historical data (hourly and daily) and preparing it for training.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import pickle

logger = logging.getLogger(__name__)


def load_hourly_normals(file_path: str) -> pd.DataFrame:
    """
    Load hourly normals data from CSV.
    
    Args:
        file_path: Path to hourly normals CSV file
    
    Returns:
        DataFrame with processed hourly data
    """
    logger.info(f"Loading hourly normals from {file_path}")
    
    df = pd.read_csv(file_path)
    
    # Parse date column
    df['DATE'] = pd.to_datetime(df['DATE'], format='%m-%dT%H:%M:%S')
    df['DATE'] = df['DATE'].apply(lambda x: x.replace(year=2012))  # Set year to 2012
    
    # Extract time features
    df['hour'] = df['DATE'].dt.hour
    df['day_of_year'] = df['DATE'].dt.dayofyear
    df['month'] = df['DATE'].dt.month
    df['day_of_week'] = df['DATE'].dt.dayofweek
    
    # Rename columns for easier access
    column_mapping = {
        'HLY-TEMP-NORMAL': 'temperature',
        'HLY-DEWP-NORMAL': 'dewpoint',
        'HLY-WIND-AVGSPD': 'wind_speed',
        'HLY-WIND-1STDIR': 'wind_direction',
        'HLY-WIND-VCTDIR': 'wind_vector_dir',
        'HLY-WIND-VCTSPD': 'wind_vector_speed'
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df[new_col] = pd.to_numeric(df[old_col], errors='coerce')
    
    # Drop rows with missing critical data
    df = df.dropna(subset=['temperature', 'wind_speed'])
    
    # Fill missing values in other columns
    df['dewpoint'] = df['dewpoint'].fillna(df['dewpoint'].median())
    df['wind_direction'] = df['wind_direction'].fillna(df['wind_direction'].median())
    
    # Approximate humidity from dewpoint (rough conversion)
    # This is a placeholder - ideally we'd have actual humidity
    if 'humidity' not in df.columns:
        # Simple approximation: higher dewpoint = higher humidity
        df['humidity'] = np.clip(50 + (df['dewpoint'] - df['dewpoint'].median()) * 2, 0, 100)
    
    logger.info(f"Loaded {len(df)} hourly records")
    return df


def load_daily_historical(file_path: str) -> pd.DataFrame:
    """
    Load daily historical data from CSV.
    
    Args:
        file_path: Path to daily historical CSV file
    
    Returns:
        DataFrame with processed daily data
    """
    logger.info(f"Loading daily historical data from {file_path}")
    
    df = pd.read_csv(file_path)
    
    # Parse date column
    df['DATE'] = pd.to_datetime(df['DATE'])
    
    # Extract time features
    df['day_of_year'] = df['DATE'].dt.dayofyear
    df['month'] = df['DATE'].dt.month
    df['day_of_week'] = df['DATE'].dt.dayofweek
    df['year'] = df['DATE'].dt.year
    
    # Rename columns for consistency
    column_mapping = {
        'TMAX': 'temp_max',
        'TMIN': 'temp_min',
        'TAVG': 'temp_avg',
        'AWND': 'wind_avg',
        'PRCP': 'precipitation'
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df[new_col] = pd.to_numeric(df[old_col], errors='coerce')
    
    # Handle missing TAVG (calculate from TMAX and TMIN if available)
    if 'temp_avg' in df.columns:
        mask = df['temp_avg'].isna()
        if 'temp_max' in df.columns and 'temp_min' in df.columns:
            df.loc[mask, 'temp_avg'] = (df.loc[mask, 'temp_max'] + df.loc[mask, 'temp_min']) / 2
    
    # Use temp_avg as temperature for consistency
    if 'temp_avg' in df.columns:
        df['temperature'] = df['temp_avg']
    
    # Fill missing values
    numeric_cols = ['temp_max', 'temp_min', 'temp_avg', 'temperature', 'wind_avg', 'precipitation']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())
    
    # Sort by date
    df = df.sort_values('DATE').reset_index(drop=True)
    
    logger.info(f"Loaded {len(df)} daily records from {df['DATE'].min()} to {df['DATE'].max()}")
    return df


def create_lstm_sequences(
    data: pd.DataFrame,
    lookback: int = 24,
    forecast_horizon: int = 24,
    features: Optional[List[str]] = None,
    target: str = 'temperature'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sequences for LSTM training.
    
    Args:
        data: DataFrame with time series data
        lookback: Number of timesteps to look back
        forecast_horizon: Number of timesteps to predict ahead
        features: List of feature column names (default: auto-detect)
        target: Target column name
    
    Returns:
        Tuple of (X, y) arrays where:
        - X: shape (samples, lookback, features)
        - y: shape (samples, forecast_horizon)
    """
    if features is None:
        # Default features for raw data (what we train on)
        features = ['temperature', 'humidity', 'wind_speed', 'wind_direction']
        # Filter to only columns that exist
        features = [f for f in features if f in data.columns]
    
    if target not in data.columns:
        raise ValueError(f"Target column '{target}' not found in data")
    
    # Ensure data is sorted by date
    if 'DATE' in data.columns:
        data = data.sort_values('DATE').reset_index(drop=True)
    
    # Extract feature and target arrays
    feature_data = data[features].values
    target_data = data[target].values
    
    X, y = [], []
    
    for i in range(len(data) - lookback - forecast_horizon + 1):
        X.append(feature_data[i:i+lookback])
        y.append(target_data[i+lookback:i+lookback+forecast_horizon])
    
    X = np.array(X)
    y = np.array(y)
    
    logger.info(f"Created {len(X)} sequences: X shape {X.shape}, y shape {y.shape}")
    return X, y


def prepare_prophet_data(
    data: pd.DataFrame,
    date_col: str = 'DATE',
    target_col: str = 'temp_max'
) -> pd.DataFrame:
    """
    Prepare data for Prophet model.
    
    Args:
        data: DataFrame with time series data
        date_col: Name of date column
        target_col: Name of target column
    
    Returns:
        DataFrame with columns 'ds' (date) and 'y' (target)
    """
    if date_col not in data.columns:
        raise ValueError(f"Date column '{date_col}' not found")
    if target_col not in data.columns:
        raise ValueError(f"Target column '{target_col}' not found")
    
    prophet_data = pd.DataFrame({
        'ds': pd.to_datetime(data[date_col]),
        'y': pd.to_numeric(data[target_col], errors='coerce')
    })
    
    # Remove missing values
    prophet_data = prophet_data.dropna()
    
    # Sort by date
    prophet_data = prophet_data.sort_values('ds').reset_index(drop=True)
    
    logger.info(f"Prepared {len(prophet_data)} records for Prophet")
    return prophet_data


def prepare_xgboost_features(
    data: pd.DataFrame,
    target_col: str = 'temp_max',
    lookback_days: int = 7
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare features for XGBoost training using RAW features.
    
    Args:
        data: DataFrame with time series data
        target_col: Name of target column (to predict)
        lookback_days: Number of days to look back for lag features
    
    Returns:
        Tuple of (X, y) where X is features DataFrame and y is target Series
    """
    df = data.copy()
    
    # Ensure sorted by date
    if 'DATE' in df.columns:
        df = df.sort_values('DATE').reset_index(drop=True)
    
    # Create lag features
    if target_col in df.columns:
        for lag in [1, 3, 7]:
            df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
        
        # Rolling statistics
        df[f'{target_col}_rolling_mean_7'] = df[target_col].rolling(window=7).mean()
        df[f'{target_col}_rolling_std_7'] = df[target_col].rolling(window=7).std()
    
    # Select feature columns (RAW features for training)
    feature_cols = []
    
    # Time features
    time_features = ['hour', 'day_of_year', 'month', 'day_of_week', 'year']
    feature_cols.extend([f for f in time_features if f in df.columns])
    
    # Weather features (RAW - what we train on)
    weather_features = ['temp_max', 'temp_min', 'temp_avg', 'temperature', 
                       'wind_avg', 'wind_speed', 'precipitation',
                       'humidity', 'dewpoint', 'wind_direction']
    feature_cols.extend([f for f in weather_features if f in df.columns])
    
    # Lag features
    lag_features = [col for col in df.columns if '_lag_' in col or '_rolling_' in col]
    feature_cols.extend(lag_features)
    
    # Remove duplicates
    feature_cols = list(set(feature_cols))
    
    # Create target (next day's value)
    if target_col in df.columns:
        y = df[target_col].shift(-1)
    else:
        raise ValueError(f"Target column '{target_col}' not found")
    
    # Select features
    X = df[feature_cols].copy()
    
    # Remove rows with missing values
    valid_idx = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_idx]
    y = y[valid_idx]
    
    logger.info(f"Prepared {len(X)} samples with {len(feature_cols)} RAW features for XGBoost")
    return X, y


def split_time_series(
    data: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    date_col: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split time series data into train/validation/test sets.
    Uses time-based splitting (NO SHUFFLING) to preserve temporal order.
    
    CRITICAL: This preserves temporal order to avoid data leakage.
    Training on future data to predict the past would be invalid.
    
    Args:
        data: DataFrame to split (must be sorted by time)
        train_ratio: Proportion for training (default: 0.7 = 70%)
        val_ratio: Proportion for validation (default: 0.15 = 15%)
        test_ratio: Proportion for testing (default: 0.15 = 15%)
        date_col: Optional date column name to ensure sorting
    
    Returns:
        Tuple of (train, val, test) DataFrames
    
    Example:
        For 1000 samples with default ratios:
        - Train: samples 0-699 (70%) - earliest data
        - Val: samples 700-849 (15%) - middle data
        - Test: samples 850-999 (15%) - latest data
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        f"Ratios must sum to 1.0, got {train_ratio + val_ratio + test_ratio}"
    
    # Ensure data is sorted by time
    if date_col and date_col in data.columns:
        data = data.sort_values(date_col).reset_index(drop=True)
    elif 'DATE' in data.columns:
        data = data.sort_values('DATE').reset_index(drop=True)
    elif 'window_start' in data.columns:
        data = data.sort_values('window_start').reset_index(drop=True)
    
    n = len(data)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    
    # Time-based split (NO SHUFFLING!)
    train_data = data.iloc[:train_end].copy()
    val_data = data.iloc[train_end:val_end].copy()
    test_data = data.iloc[val_end:].copy()
    
    # Log date ranges if available
    date_col_to_use = date_col or ('DATE' if 'DATE' in data.columns else 
                                   ('window_start' if 'window_start' in data.columns else None))
    
    if date_col_to_use:
        logger.info(f"Train period: {train_data[date_col_to_use].min()} to {train_data[date_col_to_use].max()}")
        logger.info(f"Val period: {val_data[date_col_to_use].min()} to {val_data[date_col_to_use].max()}")
        logger.info(f"Test period: {test_data[date_col_to_use].min()} to {test_data[date_col_to_use].max()}")
    
    logger.info(f"Time-series split (NO SHUFFLING): Train={len(train_data)} ({train_ratio*100:.1f}%), "
                f"Val={len(val_data)} ({val_ratio*100:.1f}%), Test={len(test_data)} ({test_ratio*100:.1f}%)")
    
    return train_data, val_data, test_data


def save_scaler(scaler: StandardScaler, file_path: str):
    """Save a scaler to disk."""
    with open(file_path, 'wb') as f:
        pickle.dump(scaler, f)
    logger.info(f"Saved scaler to {file_path}")


def load_scaler(file_path: str) -> StandardScaler:
    """Load a scaler from disk."""
    with open(file_path, 'rb') as f:
        scaler = pickle.load(f)
    logger.info(f"Loaded scaler from {file_path}")
    return scaler

