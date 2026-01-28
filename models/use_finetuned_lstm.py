"""
Example script demonstrating how to use a fine-tuned LSTM model.
This script loads a fine-tuned model, evaluates it on the test set,
and shows example inputs and outputs.
"""

import os
import sys
import argparse
import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ray.training.data_loader import (
    load_hourly_normals,
    create_lstm_sequences
)
from src.ray.models.model_loader import MODEL_BASE_PATH
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_finetuned_model(model_path: str):
    """
    Load a fine-tuned LSTM model and its associated artifacts.
    
    Args:
        model_path: Path to fine-tuned model directory
    
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
    try:
        import tensorflow as tf
        from tensorflow import keras
    except ImportError:
        raise ImportError("TensorFlow is required for LSTM models")
    
    model_file = model_path / "model.h5"
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    
    try:
        model = keras.models.load_model(str(model_file))
    except (ValueError, TypeError) as e:
        logger.warning(f"Standard load failed, trying with compile=False: {e}")
        model = keras.models.load_model(str(model_file), compile=False)
        # Recompile
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    
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
    
    logger.info(f"Loaded fine-tuned model from {model_path}")
    logger.info(f"Model version: {metadata.get('version', 'unknown')}")
    logger.info(f"Pretrained from: {metadata.get('pretrained_version', 'unknown')}")
    
    return model, scaler_X, scaler_y, metadata


def prepare_test_data(
    hourly_data_path: str,
    metadata: Dict,
    test_ratio: float = 0.15
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Prepare test data matching the model's expected format.
    
    Args:
        hourly_data_path: Path to hourly normals CSV
        metadata: Model metadata containing features and parameters
        test_ratio: Ratio of data to use for testing
    
    Returns:
        Tuple of (X_test, y_test, data_df)
    """
    # Load hourly data
    logger.info(f"Loading hourly data from {hourly_data_path}...")
    data = load_hourly_normals(hourly_data_path)
    
    # Get model parameters from metadata
    features = metadata.get('features', ['temperature', 'wind_speed', 'dewpoint'])
    target = metadata.get('target', 'temperature')
    lookback = metadata.get('lookback', 7)
    forecast_horizon = metadata.get('forecast_horizon', 7)
    
    logger.info(f"Model expects: features={features}, lookback={lookback}, forecast_horizon={forecast_horizon}")
    
    # Filter features to only those that exist
    features = [f for f in features if f in data.columns]
    
    # Create sequences
    logger.info("Creating sequences...")
    X, y = create_lstm_sequences(
        data=data,
        lookback=lookback,
        forecast_horizon=forecast_horizon,
        features=features,
        target=target
    )
    
    logger.info(f"Created {len(X)} sequences: X shape {X.shape}, y shape {y.shape}")
    
    # Split to get test set (last portion)
    n_samples = len(X)
    test_start = int(n_samples * (1 - test_ratio))
    
    X_test = X[test_start:]
    y_test = y[test_start:]
    
    logger.info(f"Test set: {len(X_test)} samples")
    logger.info(f"  X_test shape: {X_test.shape}")
    logger.info(f"  y_test shape: {y_test.shape}")
    
    return X_test, y_test, data


def evaluate_model(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    scaler_X,
    scaler_y,
    metadata: Dict
) -> Dict:
    """
    Evaluate the model on test data and calculate metrics.
    
    Args:
        model: Trained LSTM model
        X_test: Test input sequences
        y_test: Test target sequences
        scaler_X: Feature scaler
        scaler_y: Target scaler
        metadata: Model metadata
    
    Returns:
        Dictionary of evaluation metrics
    """
    logger.info("Evaluating model on test set...")
    
    # Normalize test data
    X_test_flat = X_test.reshape(-1, X_test.shape[-1])
    X_test_scaled = scaler_X.transform(X_test_flat).reshape(X_test.shape)
    
    # Make predictions
    logger.info("Making predictions...")
    y_pred_scaled = model.predict(X_test_scaled, verbose=0)
    
    # Inverse transform predictions only (y_test is already in original scale)
    y_pred_flat = y_pred_scaled.reshape(-1, 1)
    y_pred = scaler_y.inverse_transform(y_pred_flat).reshape(y_test.shape)
    
    # y_test is already in original scale from prepare_test_data, no need to transform
    y_test_original = y_test.copy()
    
    # Log some diagnostic info
    logger.info(f"Prediction range (scaled): [{y_pred_scaled.min():.2f}, {y_pred_scaled.max():.2f}]")
    logger.info(f"Prediction range (original): [{y_pred.min():.2f}, {y_pred.max():.2f}]")
    logger.info(f"True value range (original): [{y_test_original.min():.2f}, {y_test_original.max():.2f}]")
    
    # Calculate metrics (using first timestep for 1-step ahead forecast)
    if len(y_test_original.shape) > 1:
        y_true_1step = y_test_original[:, 0]
        y_pred_1step = y_pred[:, 0]
    else:
        y_true_1step = y_test_original
        y_pred_1step = y_pred
    
    # Calculate metrics
    mae = np.mean(np.abs(y_true_1step - y_pred_1step))
    rmse = np.sqrt(np.mean((y_true_1step - y_pred_1step) ** 2))
    mse = np.mean((y_true_1step - y_pred_1step) ** 2)
    
    # MAPE (handle near-zero values)
    mask = np.abs(y_true_1step) > 1e-6
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true_1step[mask] - y_pred_1step[mask]) / y_true_1step[mask])) * 100
    else:
        mape = 0.0
    
    # R² score
    ss_res = np.sum((y_true_1step - y_pred_1step) ** 2)
    ss_tot = np.sum((y_true_1step - np.mean(y_true_1step)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # Directional accuracy
    if len(y_true_1step) > 1:
        true_direction = np.diff(y_true_1step) > 0
        pred_direction = np.diff(y_pred_1step) > 0
        directional_accuracy = np.mean(true_direction == pred_direction) * 100
    else:
        directional_accuracy = 0.0
    
    metrics = {
        'mae': float(mae),
        'rmse': float(rmse),
        'mse': float(mse),
        'mape': float(mape),
        'r2': float(r2),
        'directional_accuracy': float(directional_accuracy),
        'n_samples': len(X_test)
    }
    
    logger.info("Test Set Metrics:")
    logger.info(f"  MAE: {metrics['mae']:.2f}")
    logger.info(f"  RMSE: {metrics['rmse']:.2f}")
    logger.info(f"  MAPE: {metrics['mape']:.2f}%")
    logger.info(f"  R²: {metrics['r2']:.4f}")
    logger.info(f"  Directional Accuracy: {metrics['directional_accuracy']:.2f}%")
    
    return metrics, y_test_original, y_pred


def show_examples(
    X_test: np.ndarray,
    y_test: np.ndarray,
    y_pred: np.ndarray,
    metadata: Dict,
    n_examples: int = 5,
    output_dir: str = "models/example_outputs"
):
    """
    Show example inputs and outputs from the model.
    
    Args:
        X_test: Test input sequences
        y_test: True target values
        y_pred: Predicted values
        metadata: Model metadata
        n_examples: Number of examples to show
        output_dir: Directory to save visualizations
    """
    logger.info(f"Showing {n_examples} examples...")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    features = metadata.get('features', [])
    lookback = metadata.get('lookback', 7)
    forecast_horizon = metadata.get('forecast_horizon', 7)
    
    # Show examples
    for i in range(min(n_examples, len(X_test))):
        logger.info(f"\n--- Example {i+1} ---")
        
        # Input sequence (last lookback timesteps)
        X_example = X_test[i]  # Shape: (lookback, n_features)
        logger.info(f"Input sequence (last {lookback} timesteps):")
        logger.info(f"  Shape: {X_example.shape}")
        
        # Show input features
        for t in range(lookback):
            feature_values = {feat: X_example[t, j] for j, feat in enumerate(features)}
            logger.info(f"  Timestep {t+1}: {feature_values}")
        
        # True and predicted outputs
        y_true_example = y_test[i]  # Shape: (forecast_horizon,)
        y_pred_example = y_pred[i]   # Shape: (forecast_horizon,)
        
        logger.info(f"\nTrue vs Predicted (next {forecast_horizon} timesteps):")
        for t in range(forecast_horizon):
            error = abs(y_true_example[t] - y_pred_example[t])
            logger.info(f"  Step {t+1}: True={y_true_example[t]:.2f}, Pred={y_pred_example[t]:.2f}, Error={error:.2f}")
        
        # Calculate error for this example
        mae_example = np.mean(np.abs(y_true_example - y_pred_example))
        logger.info(f"  Example MAE: {mae_example:.2f}")
    
    # Create visualization
    logger.info("\nCreating visualization...")
    create_visualization(y_test, y_pred, metadata, output_path)


def create_visualization(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    metadata: Dict,
    output_path: Path
):
    """
    Create visualization plots for the predictions.
    
    Args:
        y_test: True target values
        y_pred: Predicted values
        metadata: Model metadata
        output_path: Path to save plots
    """
    # Use first timestep for visualization
    if len(y_test.shape) > 1:
        y_true_1step = y_test[:, 0]
        y_pred_1step = y_pred[:, 0]
    else:
        y_true_1step = y_test
        y_pred_1step = y_pred
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(f"Fine-Tuned LSTM Model Evaluation\n{metadata.get('version', 'Unknown Version')}", fontsize=16)
    
    # 1. Time series plot
    ax1 = axes[0, 0]
    n_show = min(200, len(y_true_1step))  # Show first 200 points
    ax1.plot(y_true_1step[:n_show], label='True', alpha=0.7, linewidth=2)
    ax1.plot(y_pred_1step[:n_show], label='Predicted', alpha=0.7, linewidth=2)
    ax1.set_xlabel('Sample Index')
    ax1.set_ylabel('Temperature')
    ax1.set_title('Time Series: True vs Predicted (First 200 Samples)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Scatter plot
    ax2 = axes[0, 1]
    ax2.scatter(y_true_1step, y_pred_1step, alpha=0.5, s=10)
    # Perfect prediction line
    min_val = min(y_true_1step.min(), y_pred_1step.min())
    max_val = max(y_true_1step.max(), y_pred_1step.max())
    ax2.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect Prediction')
    ax2.set_xlabel('True Temperature')
    ax2.set_ylabel('Predicted Temperature')
    ax2.set_title('Scatter Plot: True vs Predicted')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Residuals plot
    ax3 = axes[1, 0]
    residuals = y_true_1step - y_pred_1step
    ax3.scatter(y_pred_1step, residuals, alpha=0.5, s=10)
    ax3.axhline(y=0, color='r', linestyle='--')
    ax3.set_xlabel('Predicted Temperature')
    ax3.set_ylabel('Residuals (True - Predicted)')
    ax3.set_title('Residuals Plot')
    ax3.grid(True, alpha=0.3)
    
    # 4. Error distribution
    ax4 = axes[1, 1]
    errors = np.abs(residuals)
    ax4.hist(errors, bins=50, alpha=0.7, edgecolor='black')
    ax4.axvline(errors.mean(), color='r', linestyle='--', label=f'Mean: {errors.mean():.2f}')
    ax4.set_xlabel('Absolute Error')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Error Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    plot_path = output_path / f"{metadata.get('version', 'model')}_evaluation.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    logger.info(f"Saved visualization to {plot_path}")
    plt.close()


def find_latest_finetuned_model(base_path: str = None) -> str:
    """
    Find the latest fine-tuned LSTM model.
    
    Args:
        base_path: Base path to search (default: MODEL_BASE_PATH/forecasting)
    
    Returns:
        Path to latest fine-tuned model directory
    """
    if base_path is None:
        base_path = Path(MODEL_BASE_PATH) / "forecasting"
    else:
        base_path = Path(base_path)
    
    if not base_path.exists():
        return None
    
    # Find all LSTM_FineTuned directories
    finetuned_models = list(base_path.glob("LSTM_FineTuned_*"))
    
    if not finetuned_models:
        return None
    
    # Sort by modification time (newest first)
    finetuned_models.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    return str(finetuned_models[0])


def find_latest_finetuned_model(base_path: str = None) -> str:
    """
    Find the latest fine-tuned LSTM model.
    
    Args:
        base_path: Base path to search (default: MODEL_BASE_PATH/forecasting)
    
    Returns:
        Path to latest fine-tuned model directory, or None if not found
    """
    if base_path is None:
        base_path = Path(MODEL_BASE_PATH) / "forecasting"
    else:
        base_path = Path(base_path)
    
    if not base_path.exists():
        logger.warning(f"Model directory does not exist: {base_path}")
        return None
    
    # Find all LSTM_FineTuned directories
    finetuned_models = list(base_path.glob("LSTM_FineTuned_*"))
    
    if not finetuned_models:
        logger.warning(f"No fine-tuned models found in {base_path}")
        return None
    
    # Sort by modification time (newest first)
    finetuned_models.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    return str(finetuned_models[0])


def main():
    parser = argparse.ArgumentParser(
        description="Use and evaluate a fine-tuned LSTM model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect latest fine-tuned model:
  python models/use_finetuned_lstm.py --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv
  
  # Specify model path:
  python models/use_finetuned_lstm.py \\
      --model-path models/trained/forecasting/LSTM_FineTuned_20260124_193541 \\
      --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv
        """
    )
    parser.add_argument("--model-path", type=str, default=None,
                       help="Path to fine-tuned model directory (default: auto-detect latest)")
    parser.add_argument("--hourly-data", type=str, required=True,
                       help="Path to hourly normals CSV")
    parser.add_argument("--n-examples", type=int, default=5,
                       help="Number of examples to show (default: 5)")
    parser.add_argument("--output-dir", type=str, default="models/example_outputs",
                       help="Directory to save outputs (default: models/example_outputs)")
    
    args = parser.parse_args()
    
    # Auto-detect model if not provided
    if args.model_path is None:
        logger.info("No model path provided, searching for latest fine-tuned model...")
        args.model_path = find_latest_finetuned_model()
        if args.model_path is None:
            logger.error("=" * 60)
            logger.error("ERROR: No fine-tuned models found!")
            logger.error("=" * 60)
            logger.error("Please specify --model-path with the path to your fine-tuned model.")
            logger.error("")
            logger.error("Example:")
            logger.error("  python models/use_finetuned_lstm.py \\")
            logger.error("      --model-path models/trained/forecasting/LSTM_FineTuned_20260124_193541 \\")
            logger.error("      --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv")
            logger.error("")
            logger.error("Or fine-tune a model first:")
            logger.error("  python src/ray/training/finetune_lstm_hourly.py \\")
            logger.error("      --pretrained-model models/trained/forecasting/LSTM_20260124_184927 \\")
            logger.error("      --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv")
            return
        logger.info(f"✓ Found latest fine-tuned model: {args.model_path}")
    else:
        # Validate that the provided path exists
        if not Path(args.model_path).exists():
            logger.error(f"Model path does not exist: {args.model_path}")
            logger.error("Please check the path and try again.")
            return
    
    # Load model
    logger.info("=" * 60)
    logger.info("Loading Fine-Tuned LSTM Model")
    logger.info("=" * 60)
    model, scaler_X, scaler_y, metadata = load_finetuned_model(args.model_path)
    
    # Prepare test data
    logger.info("\n" + "=" * 60)
    logger.info("Preparing Test Data")
    logger.info("=" * 60)
    X_test, y_test, data = prepare_test_data(
        args.hourly_data,
        metadata,
        test_ratio=0.15
    )
    
    # Evaluate model
    logger.info("\n" + "=" * 60)
    logger.info("Model Evaluation")
    logger.info("=" * 60)
    metrics, y_test_original, y_pred = evaluate_model(
        model, X_test, y_test, scaler_X, scaler_y, metadata
    )
    
    # Show examples
    logger.info("\n" + "=" * 60)
    logger.info("Example Inputs and Outputs")
    logger.info("=" * 60)
    show_examples(
        X_test, y_test_original, y_pred, metadata,
        n_examples=args.n_examples,
        output_dir=args.output_dir
    )
    
    # Save metrics
    metrics_path = Path(args.output_dir) / f"{metadata.get('version', 'model')}_test_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"\nSaved metrics to {metrics_path}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Evaluation Complete!")
    logger.info("=" * 60)
    logger.info(f"\nSummary:")
    logger.info(f"  Model: {metadata.get('version', 'unknown')}")
    logger.info(f"  Pretrained from: {metadata.get('pretrained_version', 'unknown')}")
    logger.info(f"  Test Samples: {metrics['n_samples']}")
    logger.info(f"  MAE: {metrics['mae']:.2f}")
    logger.info(f"  RMSE: {metrics['rmse']:.2f}")
    logger.info(f"  MAPE: {metrics['mape']:.2f}%")
    logger.info(f"  R²: {metrics['r2']:.4f}")
    logger.info(f"  Directional Accuracy: {metrics['directional_accuracy']:.2f}%")


if __name__ == "__main__":
    main()

