# Model Benchmarking Guide

This guide explains how to use the `benchmark_models.py` script to evaluate trained forecasting models.

## Overview

The benchmark script:
- ✅ Tests models on test set (using same train/val/test split as training)
- ✅ Calculates comprehensive metrics (MAE, RMSE, MAPE, R², directional accuracy)
- ✅ Saves results to JSON files
- ✅ Creates visualizations (time series, scatter plots, residual analysis, error distributions)
- ✅ Compares multiple models side-by-side

## Requirements

```bash
pip install pandas numpy matplotlib seaborn scikit-learn tensorflow xgboost prophet
```

## Usage

### 1. **Benchmark a Single Model**

```bash
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --model models/trained/forecasting/XGBoost_20260124_184642 \
    --output models/benchmark_results
```

### 2. **Benchmark All Models**

```bash
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --output models/benchmark_results
```

This will automatically find all models in `models/trained/forecasting/` and benchmark them.

### 3. **With Custom Model Path**

```bash
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --model-base-path /path/to/models \
    --output models/benchmark_results
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--data` | Yes | Path to data CSV file (daily or hourly) |
| `--model` | No | Path to specific model directory (if omitted, benchmarks all) |
| `--output` | No | Output directory (default: `models/benchmark_results`) |
| `--model-base-path` | No | Base path for models (default: from `model_loader.py`) |

## Output

The benchmark script creates:

### 1. **Results JSON Files**
- `{model_name}_benchmark_results.json` - Detailed metrics for each model

### 2. **Visualizations**
- `{model_name}_timeseries.png` - Time series plot (true vs predicted)
- `{model_name}_scatter.png` - Scatter plot (true vs predicted)
- `{model_name}_residuals.png` - Residual analysis
- `{model_name}_error_dist.png` - Error distribution histogram

### 3. **Comparison Files**
- `model_comparison.csv` - Side-by-side comparison of all models
- `model_comparison.png` - Bar chart comparing MAE and RMSE

## Metrics Explained

| Metric | Description | Best Value |
|--------|-------------|------------|
| **MAE** | Mean Absolute Error | Lower is better |
| **RMSE** | Root Mean Squared Error | Lower is better |
| **MAPE** | Mean Absolute Percentage Error | Lower is better |
| **R²** | Coefficient of Determination | Higher is better (max 1.0) |
| **Directional Accuracy** | % of correct direction predictions | Higher is better (max 100%) |
| **Mean Error** | Average bias (predicted - true) | Closer to 0 is better |
| **Std Error** | Standard deviation of errors | Lower is better |

## Example Output

```
INFO:__main__:============================================================
INFO:__main__:Benchmark Results for XGBoost_20260124_184642
INFO:__main__:============================================================
INFO:__main__:MAE:  3.1100°F
INFO:__main__:RMSE: 4.0100°F
INFO:__main__:MAPE: 54.64%
INFO:__main__:R²:   0.9234
INFO:__main__:Directional Accuracy: 67.23%
INFO:__main__:============================================================
```

## Visualizations

### Time Series Plot
Shows how well the model tracks the true values over time.

### Scatter Plot
Shows the correlation between true and predicted values. Points closer to the red diagonal line indicate better predictions.

### Residual Analysis
- **Left plot**: Residuals vs predicted values (should be random scatter around 0)
- **Right plot**: Distribution of residuals (should be centered at 0, normally distributed)

### Error Distribution
Shows the distribution of absolute errors. Lower mean/median indicates better performance.

## Tips

1. **Compare Models**: Use `--output` to save all results in one directory for easy comparison
2. **Check Residuals**: If residuals show patterns (not random), the model may be missing important features
3. **Directional Accuracy**: Important for time series - shows if model captures trends correctly
4. **R² Score**: Values close to 1.0 indicate the model explains most of the variance

## Troubleshooting

### Error: "Model file not found"
- Check that the model directory contains `model.pkl` (XGBoost/Prophet) or `model.h5` (LSTM)
- Ensure `metadata.json` exists in the model directory

### Error: "Scalers not found" (LSTM)
- LSTM models require `scaler_X.pkl` and `scaler_y.pkl`
- These should be saved during training

### Error: "Unknown model type"
- Check that `metadata.json` contains a `model_type` field
- Should be one of: "xgboost", "lstm", "prophet"

## Example: Complete Benchmark Workflow

```bash
# 1. Train models (if not already done)
python src/ray/training/train_xgboost.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv

python src/ray/training/train_lstm.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --use-gpu --mixed-precision

python src/ray/training/train_prophet.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv

# 2. Benchmark all models
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --output models/benchmark_results

# 3. View results
# - Check models/benchmark_results/model_comparison.csv
# - View PNG files in models/benchmark_results/
```

## Notes

- The benchmark uses the **same train/val/test split** as training to ensure fair comparison
- Test set is **never seen during training** (proper holdout set)
- All metrics are calculated on the **test set only** (not train or validation)

