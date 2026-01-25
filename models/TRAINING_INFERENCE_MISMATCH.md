# Training on Raw Data, Inferring on Aggregated Data

## Overview

This document explains how we train models on **raw historical data** (with more variables) but infer on **Spark-aggregated data** (with aggregated features). This is a common pattern in production ML systems.

## The Problem

- **Training Data**: Raw historical data with variables like:
  - `temperature`, `humidity`, `pressure`, `wind_speed`, `wind_direction`
  
- **Inference Data**: Spark-aggregated data with variables like:
  - `temperature_mean`, `humidity_mean`, `pressure_mean`, `wind_speed_mean`, `wind_direction_mean`

## The Solution: Feature Adapter

We use a **Feature Adapter** that converts Spark-aggregated features to raw features at inference time.

### How It Works

1. **Training Phase**:
   - Load raw historical data (temperature, humidity, pressure, etc.)
   - Train model on these raw features
   - Save model + feature adapter

2. **Inference Phase**:
   - Receive Spark-aggregated features (temperature_mean, humidity_mean, etc.)
   - Use feature adapter to convert: `temperature_mean` → `temperature`
   - Feed converted features to model

### Feature Mapping

The adapter maps aggregated features to raw features:

```python
# Spark aggregated → Raw (for model)
temperature_mean → temperature
humidity_mean → humidity
pressure_mean → sea_level_pressure
wind_speed_mean → wind_speed
wind_direction_mean → wind_direction
precipitation_mean → precipitation
```

## Benefits

1. **More Training Data**: Raw historical data has more detailed information
2. **Production-Ready**: Inference uses aggregated data from Spark (what's actually available)
3. **Flexibility**: Can train on any historical dataset, regardless of aggregation format
4. **Separation of Concerns**: Training and inference data formats are decoupled

## Implementation

### Training

```bash
# Train on raw historical data
python src/ray/training/train_lstm.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --epochs 50 \
    --use-gpu --mixed-precision
```

The training script:
- Loads raw data (temperature, humidity, etc.)
- Trains model on raw features
- Saves model + feature adapter

### Inference

```python
from src.ray.training.feature_adapter import FeatureAdapter
import pickle

# Load feature adapter
with open('models/forecasting/v1.0/feature_adapter.pkl', 'rb') as f:
    adapter = pickle.load(f)

# Spark aggregated features (from Kafka)
spark_features = {
    'temperature_mean': 45.0,
    'humidity_mean': 65.0,
    'pressure_mean': 1012.0,
    'wind_speed_mean': 8.0,
    'wind_direction_mean': 230.0
}

# Convert to raw features
raw_features = adapter.adapt_features(spark_features)
# Result: {'temperature': 45.0, 'humidity': 65.0, 'sea_level_pressure': 1012.0, ...}

# Use with model
prediction = model.predict(raw_features)
```

## Data Splitting

**CRITICAL**: We use time-series splitting (NO SHUFFLING):

- **Train**: 70% (earliest data)
- **Validation**: 15% (middle data)
- **Test**: 15% (latest data)

This prevents data leakage (using future data to predict the past).

## Files

- `src/ray/training/feature_adapter.py`: Feature adapter implementation
- `src/ray/training/train_lstm.py`: LSTM training (saves adapter)
- `src/ray/training/train_xgboost.py`: XGBoost training (saves adapter)
- `src/ray/training/train_prophet.py`: Prophet training

## Model Artifacts

Each trained model includes:
- `model.h5` or `model.pkl`: The trained model
- `feature_adapter.pkl`: Feature adapter for inference
- `scaler_X.pkl`, `scaler_y.pkl`: Data scalers (for LSTM)
- `metadata.json`: Training metadata

## Example Usage

```python
# At inference time (in InferenceActor)
import pickle
from src.ray.training.feature_adapter import FeatureAdapter

# Load model and adapter
model = load_model('models/forecasting/v1.0/model.h5')
with open('models/forecasting/v1.0/feature_adapter.pkl', 'rb') as f:
    adapter = pickle.load(f)

# Get Spark aggregated features from Kafka
spark_features = message.value  # From weather-features topic

# Convert to raw features
raw_features = adapter.adapt_features(spark_features)

# Predict
prediction = model.predict(raw_features)
```

## Notes

- The feature adapter uses mean values as representative values (e.g., `temperature_mean` → `temperature`)
- Additional aggregated features (std, min, max) are preserved if available
- Default values are used for missing features
- The adapter is saved with each model version for consistency

