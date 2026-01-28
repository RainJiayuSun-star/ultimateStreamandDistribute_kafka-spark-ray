"""
Benchmark script for evaluating trained forecasting models.
Tests models on test set, calculates metrics, saves results, and creates visualizations.
"""

import os
import sys
import argparse
import logging
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ray.training.data_loader import (
    load_daily_historical,
    load_hourly_normals,
    prepare_xgboost_features,
    prepare_prophet_data,
    create_lstm_sequences,
    split_time_series
)
from src.ray.models.model_loader import MODEL_BASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import seaborn (optional, only for styling)
try:
    import seaborn as sns
    sns.set_style("whitegrid")
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    logger.warning("seaborn not available. Plots will use default matplotlib style.")

# Set style for plots
plt.rcParams['figure.figsize'] = (12, 6)


def load_model(model_path: Path) -> Tuple[Any, Dict]:
    """
    Load a trained model and its metadata.
    
    Args:
        model_path: Path to model directory
    
    Returns:
        Tuple of (model, metadata)
    """
    metadata_path = model_path / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    model_type = metadata.get('model_type', '').lower()
    
    if 'xgboost' in model_type:
        # Load XGBoost model
        model_file = model_path / "model.pkl"
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        with open(model_file, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Loaded XGBoost model from {model_path}")
    
    elif 'lstm' in model_type:
        # Load LSTM model
        try:
            import tensorflow as tf
            from tensorflow import keras
        except ImportError:
            raise ImportError("TensorFlow is required for LSTM models")
        
        model_file = model_path / "model.h5"
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        # Handle Keras version compatibility
        try:
            model = keras.models.load_model(str(model_file))
        except (ValueError, TypeError) as e:
            # Try loading with compile=False for compatibility issues
            logger.warning(f"Standard load failed, trying with compile=False: {e}")
            try:
                model = keras.models.load_model(str(model_file), compile=False)
                # Recompile with standard metrics
                model.compile(optimizer='adam', loss='mse', metrics=['mae'])
            except Exception as e2:
                logger.error(f"Failed to load LSTM model: {e2}")
                raise
        logger.info(f"Loaded LSTM model from {model_path}")
    
    elif 'prophet' in model_type:
        # Load Prophet model
        model_file = model_path / "model.pkl"
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        with open(model_file, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Loaded Prophet model from {model_path}")
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model, metadata


def load_scalers(model_path: Path) -> Tuple[Optional[Any], Optional[Any]]:
    """Load scalers for LSTM models."""
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
    
    return scaler_X, scaler_y


def prepare_test_data_xgboost(data: pd.DataFrame, target_col: str, metadata: Dict) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare test data for XGBoost using the same feature engineering as training."""
    X, y = prepare_xgboost_features(data, target_col=target_col)
    return X, y


def prepare_test_data_lstm(data: pd.DataFrame, features: List[str], target: str, 
                           lookback: int, forecast_horizon: int) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare test data for LSTM."""
    sequences, targets = create_lstm_sequences(
        data, lookback=lookback, forecast_horizon=forecast_horizon,
        features=features, target=target
    )
    return sequences, targets


def prepare_test_data_prophet(data: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Prepare test data for Prophet."""
    prophet_data = prepare_prophet_data(data, date_col='DATE', target_col=target_col)
    return prophet_data


def predict_xgboost(model: Any, X_test: pd.DataFrame) -> np.ndarray:
    """Make predictions with XGBoost model."""
    # Ensure feature order matches model's expected order
    # Get feature names from model
    if hasattr(model, 'feature_names_in_'):
        expected_features = model.feature_names_in_
    elif hasattr(model, 'get_booster'):
        # XGBoost stores feature names in the booster
        try:
            expected_features = model.get_booster().feature_names
        except:
            expected_features = None
    else:
        expected_features = None
    
    # Reorder columns if needed
    if expected_features is not None and len(expected_features) > 0:
        # Check if order matches
        if list(X_test.columns) != list(expected_features):
            logger.info(f"Reordering features to match model's expected order")
            # Only reorder columns that exist in both
            common_features = [f for f in expected_features if f in X_test.columns]
            if len(common_features) == len(expected_features):
                X_test = X_test[expected_features]
            else:
                logger.warning(f"Feature mismatch. Expected {len(expected_features)}, found {len(common_features)}")
    
    return model.predict(X_test)


def predict_lstm(model: Any, X_test: np.ndarray, scaler_y: Any) -> np.ndarray:
    """Make predictions with LSTM model."""
    predictions_scaled = model.predict(X_test, verbose=0)
    # Reshape if needed
    if len(predictions_scaled.shape) > 1:
        predictions_scaled = predictions_scaled[:, 0]  # Take first timestep
    # Inverse transform
    predictions = scaler_y.inverse_transform(predictions_scaled.reshape(-1, 1)).flatten()
    return predictions


def predict_prophet(model: Any, test_data: pd.DataFrame) -> np.ndarray:
    """Make predictions with Prophet model."""
    # Prophet needs to predict on dates that include the test period
    # Create future dataframe with test dates
    future = model.make_future_dataframe(periods=0)
    # Add test dates if they're not already in the future dataframe
    test_dates = pd.DataFrame({'ds': test_data['ds']})
    future = pd.concat([future, test_dates]).drop_duplicates(subset=['ds']).sort_values('ds')
    
    forecast = model.predict(future)
    # Get predictions for test period only
    forecast_subset = forecast[forecast['ds'].isin(test_data['ds'].values)].sort_values('ds')
    # Ensure same order as test_data
    forecast_subset = forecast_subset.set_index('ds').reindex(test_data['ds'].values).reset_index()
    predictions = forecast_subset['yhat'].values
    return predictions


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Calculate comprehensive metrics.
    
    Args:
        y_true: True values
        y_pred: Predicted values
    
    Returns:
        Dictionary of metrics
    """
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    # MAPE calculation with better handling of small values
    mask = np.abs(y_true) > 1e-6  # Only calculate MAPE for non-zero values
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    else:
        mape = 0.0
    
    # Additional metrics
    mse = np.mean((y_true - y_pred) ** 2)
    mean_error = np.mean(y_pred - y_true)  # Bias
    std_error = np.std(y_pred - y_true)    # Error spread
    
    # R-squared
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / (ss_tot + 1e-6))
    
    # Directional accuracy (for time series)
    if len(y_true) > 1:
        true_direction = np.diff(y_true) > 0
        pred_direction = np.diff(y_pred) > 0
        directional_accuracy = np.mean(true_direction == pred_direction) * 100
    else:
        directional_accuracy = 0.0
    
    return {
        'mae': float(mae),
        'rmse': float(rmse),
        'mape': float(mape),
        'mse': float(mse),
        'mean_error': float(mean_error),
        'std_error': float(std_error),
        'r2': float(r2),
        'directional_accuracy': float(directional_accuracy)
    }


def create_visualizations(y_true: np.ndarray, y_pred: np.ndarray, 
                         model_name: str, output_dir: Path, dates: Optional[pd.Series] = None):
    """
    Create visualization plots for model predictions.
    
    Args:
        y_true: True values
        y_pred: Predicted values
        model_name: Name of the model
        output_dir: Directory to save plots
        dates: Optional date series for time series plots
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Time series plot
    plt.figure(figsize=(14, 6))
    if dates is not None and len(dates) == len(y_true):
        plt.plot(dates, y_true, label='True', alpha=0.7, linewidth=1.5)
        plt.plot(dates, y_pred, label='Predicted', alpha=0.7, linewidth=1.5)
        plt.xlabel('Date', fontsize=12)
    else:
        plt.plot(y_true, label='True', alpha=0.7, linewidth=1.5)
        plt.plot(y_pred, label='Predicted', alpha=0.7, linewidth=1.5)
        plt.xlabel('Sample Index', fontsize=12)
    plt.ylabel('Temperature (°F)', fontsize=12)
    plt.title(f'{model_name} - Predictions vs True Values', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{model_name}_timeseries.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Scatter plot (True vs Predicted)
    plt.figure(figsize=(8, 8))
    plt.scatter(y_true, y_pred, alpha=0.5, s=20)
    min_val = min(np.min(y_true), np.min(y_pred))
    max_val = max(np.max(y_true), np.max(y_pred))
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect Prediction')
    plt.xlabel('True Values (°F)', fontsize=12)
    plt.ylabel('Predicted Values (°F)', fontsize=12)
    plt.title(f'{model_name} - True vs Predicted', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{model_name}_scatter.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Residual plot
    residuals = y_pred - y_true
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    plt.scatter(y_pred, residuals, alpha=0.5, s=20)
    plt.axhline(y=0, color='r', linestyle='--', linewidth=2)
    plt.xlabel('Predicted Values (°F)', fontsize=11)
    plt.ylabel('Residuals (°F)', fontsize=11)
    plt.title('Residuals vs Predicted', fontsize=12, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    plt.subplot(1, 2, 2)
    plt.hist(residuals, bins=50, alpha=0.7, edgecolor='black')
    plt.xlabel('Residuals (°F)', fontsize=11)
    plt.ylabel('Frequency', fontsize=11)
    plt.title('Residual Distribution', fontsize=12, fontweight='bold')
    plt.axvline(x=0, color='r', linestyle='--', linewidth=2)
    plt.grid(True, alpha=0.3)
    
    plt.suptitle(f'{model_name} - Residual Analysis', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / f'{model_name}_residuals.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Error distribution
    errors = np.abs(y_pred - y_true)
    plt.figure(figsize=(10, 6))
    plt.hist(errors, bins=50, alpha=0.7, edgecolor='black', color='steelblue')
    plt.axvline(x=np.mean(errors), color='r', linestyle='--', linewidth=2, 
                label=f'Mean Error: {np.mean(errors):.2f}°F')
    plt.axvline(x=np.median(errors), color='g', linestyle='--', linewidth=2,
                label=f'Median Error: {np.median(errors):.2f}°F')
    plt.xlabel('Absolute Error (°F)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'{model_name} - Error Distribution', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{model_name}_error_dist.png', dpi=300, bbox_inches='tight')
    plt.close()


def benchmark_model(model_path: str, data_path: str, output_dir: str):
    """
    Benchmark a single model on test data.
    
    Args:
        model_path: Path to model directory
        data_path: Path to data CSV file
        output_dir: Directory to save results
    """
    model_path = Path(model_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Benchmarking model from {model_path}")
    
    # Load model and metadata
    model, metadata = load_model(model_path)
    model_type = metadata.get('model_type', '').lower()
    target_col = metadata.get('target', 'temp_max')
    model_name = model_path.name
    
    logger.info(f"Model type: {model_type}, Target: {target_col}")
    
    # Load data
    logger.info(f"Loading data from {data_path}")
    if 'hourly' in data_path.lower():
        data = load_hourly_normals(data_path)
    else:
        data = load_daily_historical(data_path)
    
    # Prepare test data based on model type
    if 'xgboost' in model_type:
        # Prepare features
        X, y = prepare_xgboost_features(data, target_col=target_col)
        
        # Get expected feature order from metadata if available
        if 'features' in metadata:
            expected_features = metadata['features']
            # Reorder X to match expected feature order
            available_features = [f for f in expected_features if f in X.columns]
            if len(available_features) == len(expected_features):
                X = X[expected_features]
                logger.info(f"Reordered features to match model's expected order")
            else:
                logger.warning(f"Some expected features not found. Expected {len(expected_features)}, found {len(available_features)}")
        
        # Split data (use same split as training: 70/15/15)
        n_samples = len(X)
        train_end = int(n_samples * 0.7)
        val_end = int(n_samples * 0.85)
        
        X_test = X.iloc[val_end:]
        y_test = y.iloc[val_end:]
        dates = data['DATE'].iloc[val_end:].reset_index(drop=True)
        
        # Make predictions
        logger.info("Making predictions...")
        y_pred = predict_xgboost(model, X_test)
        
    elif 'lstm' in model_type:
        # Get model parameters from metadata
        lookback = metadata.get('lookback', 7)
        forecast_horizon = metadata.get('forecast_horizon', 7)
        features = metadata.get('features', ['temperature', 'wind_avg', 'precipitation'])
        target = metadata.get('target', 'temperature')
        
        # Create sequences
        sequences, targets = create_lstm_sequences(
            data, lookback=lookback, forecast_horizon=forecast_horizon,
            features=features, target=target
        )
        
        # Split data
        n_samples = len(sequences)
        train_end = int(n_samples * 0.7)
        val_end = int(n_samples * 0.85)
        
        X_test = sequences[val_end:]
        y_test = targets[val_end:]
        
        # Load scalers
        scaler_X, scaler_y = load_scalers(model_path)
        if scaler_X is None or scaler_y is None:
            raise ValueError("Scalers not found for LSTM model")
        
        # Scale test data (same reshaping as during training)
        # Reshape to (n_samples * lookback, n_features) for scaling
        X_test_flat = X_test.reshape(-1, X_test.shape[-1])
        X_test_scaled_flat = scaler_X.transform(X_test_flat)
        X_test_scaled = X_test_scaled_flat.reshape(X_test.shape)
        
        # Make predictions
        logger.info("Making predictions...")
        y_pred = predict_lstm(model, X_test_scaled, scaler_y)
        
        # Handle multi-step output: y_test has shape (n_samples, forecast_horizon)
        # y_pred has shape (n_samples,) - first timestep only
        # For benchmarking, use first timestep from y_test to match y_pred
        if len(y_test.shape) > 1 and y_test.shape[1] > 1:
            logger.info(f"y_test has shape {y_test.shape}, using first timestep for evaluation")
            y_test = y_test[:, 0]  # Take first timestep (1-step ahead forecast)
        
        # Get dates (approximate)
        dates = data['DATE'].iloc[val_end:val_end+len(y_test)].reset_index(drop=True)
        
    elif 'prophet' in model_type:
        # Prepare Prophet data
        prophet_data = prepare_prophet_data(data, date_col='DATE', target_col=target_col)
        
        # Split data (use same split as training: 80/10/10)
        train_data, val_data, test_data = split_time_series(
            prophet_data, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, date_col='ds'
        )
        
        y_test = test_data['y'].values
        dates = test_data['ds']
        
        # Make predictions
        logger.info("Making predictions...")
        y_pred = predict_prophet(model, test_data)
        
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    # Calculate metrics
    logger.info("Calculating metrics...")
    metrics = calculate_metrics(y_test, y_pred)
    
    # Print metrics
    logger.info("=" * 60)
    logger.info(f"Benchmark Results for {model_name}")
    logger.info("=" * 60)
    logger.info(f"MAE:  {metrics['mae']:.4f}°F")
    logger.info(f"RMSE: {metrics['rmse']:.4f}°F")
    logger.info(f"MAPE: {metrics['mape']:.2f}%")
    logger.info(f"R²:   {metrics['r2']:.4f}")
    logger.info(f"Directional Accuracy: {metrics['directional_accuracy']:.2f}%")
    logger.info("=" * 60)
    
    # Save results
    results = {
        'model_name': model_name,
        'model_type': model_type,
        'target': target_col,
        'test_samples': len(y_test),
        'metrics': metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    results_path = output_dir / f"{model_name}_benchmark_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved results to {results_path}")
    
    # Create visualizations
    logger.info("Creating visualizations...")
    create_visualizations(y_test, y_pred, model_name, output_dir, dates)
    logger.info(f"Saved visualizations to {output_dir}")
    
    return results


def benchmark_all_models(data_path: str, output_dir: str, model_base_path: Optional[str] = None):
    """
    Benchmark all models in the forecasting directory.
    
    Args:
        data_path: Path to data CSV file
        output_dir: Directory to save results
        model_base_path: Base path for models (default: from model_loader)
    """
    if model_base_path is None:
        model_base_path = MODEL_BASE_PATH
    
    forecasting_path = Path(model_base_path) / "forecasting"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Finding models in {forecasting_path}")
    
    # Find all model directories
    model_dirs = [d for d in forecasting_path.iterdir() if d.is_dir()]
    
    if not model_dirs:
        logger.warning(f"No models found in {forecasting_path}")
        return
    
    logger.info(f"Found {len(model_dirs)} models to benchmark")
    
    all_results = []
    
    for model_dir in model_dirs:
        try:
            logger.info(f"\n{'='*60}'")
            logger.info(f"Benchmarking {model_dir.name}")
            logger.info(f"{'='*60}'")
            
            results = benchmark_model(
                str(model_dir),
                data_path,
                str(output_dir)
            )
            all_results.append(results)
            
        except Exception as e:
            logger.error(f"Error benchmarking {model_dir.name}: {e}", exc_info=True)
            continue
    
    # Create comparison summary
    if all_results:
        logger.info("\n" + "=" * 60)
        logger.info("COMPARISON SUMMARY")
        logger.info("=" * 60)
        
        comparison_data = []
        for r in all_results:
            comparison_data.append({
                'Model': r['model_name'],
                'Type': r['model_type'],
                'MAE (°F)': f"{r['metrics']['mae']:.3f}",
                'RMSE (°F)': f"{r['metrics']['rmse']:.3f}",
                'MAPE (%)': f"{r['metrics']['mape']:.2f}",
                'R²': f"{r['metrics']['r2']:.4f}",
                'Dir. Acc. (%)': f"{r['metrics']['directional_accuracy']:.2f}"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        print("\n" + comparison_df.to_string(index=False))
        
        # Save comparison
        comparison_path = output_dir / "model_comparison.csv"
        comparison_df.to_csv(comparison_path, index=False)
        logger.info(f"\nSaved comparison to {comparison_path}")
        
        # Create comparison visualization
        create_comparison_plot(all_results, output_dir)
    
    logger.info("\nBenchmarking completed!")


def create_comparison_plot(results: List[Dict], output_dir: Path):
    """Create a comparison plot of all models."""
    model_names = [r['model_name'] for r in results]
    mae_values = [r['metrics']['mae'] for r in results]
    rmse_values = [r['metrics']['rmse'] for r in results]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # MAE comparison
    ax1.barh(model_names, mae_values, color='steelblue', alpha=0.7)
    ax1.set_xlabel('MAE (°F)', fontsize=12)
    ax1.set_title('Mean Absolute Error Comparison', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')
    
    # RMSE comparison
    ax2.barh(model_names, rmse_values, color='coral', alpha=0.7)
    ax2.set_xlabel('RMSE (°F)', fontsize=12)
    ax2.set_title('Root Mean Squared Error Comparison', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig(output_dir / "model_comparison.png", dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved comparison plot to {output_dir / 'model_comparison.png'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark trained forecasting models")
    parser.add_argument("--data", type=str, required=True, 
                       help="Path to data CSV file (daily or hourly)")
    parser.add_argument("--model", type=str, default=None,
                       help="Path to specific model directory (if None, benchmarks all models)")
    parser.add_argument("--output", type=str, default="models/benchmark_results",
                       help="Output directory for results and visualizations")
    parser.add_argument("--model-base-path", type=str, default=None,
                       help="Base path for models (default: from model_loader)")
    
    args = parser.parse_args()
    
    if args.model:
        # Benchmark single model
        benchmark_model(args.model, args.data, args.output)
    else:
        # Benchmark all models
        benchmark_all_models(args.data, args.output, args.model_base_path)

