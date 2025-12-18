# Phase 3: ML Integration with Ray - Files to Create

This document lists all files needed for Phase 3 implementation.

## Directory Structure

```
src/ray/
├── inference/
│   ├── __init__.py                    # ✅ Already exists
│   ├── ray_consumer.py                # ⬜ NEW: Kafka consumer for Ray
│   ├── inference_actor.py             # ⬜ NEW: Ray actor for ML inference
│   └── predictor.py                   # ⬜ NEW: Prediction logic wrapper
│
├── training/
│   ├── __init__.py                    # ✅ Already exists
│   ├── train_forecasting.py           # ⬜ NEW: Forecasting model training
│   ├── train_anomaly.py               # ⬜ NEW: Anomaly detection training
│   ├── data_loader.py                 # ⬜ NEW: Historical data loading
│   └── model_factory.py               # ⬜ NEW: Model creation utilities
│
└── models/
    ├── __init__.py                    # ✅ Already exists
    ├── forecasting_model.py           # ⬜ NEW: Forecasting model wrapper
    ├── anomaly_model.py               # ⬜ NEW: Anomaly detection model wrapper
    └── model_loader.py                # ⬜ NEW: Model loading utilities
```

---

## File Descriptions and Implementation Order

### Priority 1: Core Inference Pipeline (Start Here)

#### 1. `src/ray/models/model_loader.py`
**Purpose:** Load trained models from disk into memory  
**Key Functions:**
- `load_forecasting_model(model_path)` - Load forecasting model
- `load_anomaly_model(model_path)` - Load anomaly detection model
- `get_latest_model_version(model_type)` - Get latest model version
- `validate_model(model, model_type)` - Validate loaded model

**Dependencies:** None (base utility)

---

#### 2. `src/ray/models/forecasting_model.py`
**Purpose:** Wrapper class for forecasting model  
**Key Components:**
- `ForecastingModel` class
- `predict(features, horizon=24)` - Predict next N hours
- `preprocess_features(features)` - Feature preprocessing
- Model can start simple (linear regression) then upgrade to LSTM/Prophet

**Dependencies:** `model_loader.py`

---

#### 3. `src/ray/models/anomaly_model.py`
**Purpose:** Wrapper class for anomaly detection model  
**Key Components:**
- `AnomalyModel` class
- `detect_anomaly(features)` - Detect if features are anomalous
- `get_anomaly_score(features)` - Get anomaly score (0-1)
- Model can start simple (statistical thresholds) then upgrade to Isolation Forest/Autoencoder

**Dependencies:** `model_loader.py`

---

#### 4. `src/ray/inference/inference_actor.py`
**Purpose:** Ray actor that performs ML inference  
**Key Components:**
- `InferenceActor` class (Ray actor)
- `__init__()` - Load models on actor initialization
- `predict(features_dict)` - Perform forecasting + anomaly detection
- `batch_predict(features_list)` - Batch processing for efficiency
- Returns: `{"forecast": [...], "anomaly_score": float, "is_anomaly": bool}`

**Dependencies:** 
- `forecasting_model.py`
- `anomaly_model.py`
- `model_loader.py`

---

#### 5. `src/ray/inference/ray_consumer.py`
**Purpose:** Main Kafka consumer that uses Ray actors for inference  
**Key Components:**
- Connect to Ray cluster
- Create/connect to inference actors
- Consume from `weather-features` topic
- Call inference actors for predictions
- Format results and write to `weather-predictions` topic
- Handle errors and retries

**Dependencies:**
- `inference_actor.py`
- `kafka_config.py` (from utils)

**This is the main entry point for Ray inference!**

---

### Priority 2: Training Pipeline

#### 6. `src/ray/training/data_loader.py`
**Purpose:** Load and preprocess historical data for training  
**Key Functions:**
- `load_historical_data(data_path)` - Load from CSV/Parquet
- `preprocess_for_forecasting(data)` - Prepare data for forecasting model
- `preprocess_for_anomaly(data)` - Prepare data for anomaly model
- `split_train_test(data, test_size=0.2)` - Split data

**Dependencies:** pandas, numpy

---

#### 7. `src/ray/training/model_factory.py`
**Purpose:** Create model instances for training  
**Key Functions:**
- `create_forecasting_model(model_type="linear")` - Create forecasting model
- `create_anomaly_model(model_type="isolation_forest")` - Create anomaly model
- Support multiple model types (linear, LSTM, Prophet, etc.)

**Dependencies:** scikit-learn, torch (if using neural networks)

---

#### 8. `src/ray/training/train_forecasting.py`
**Purpose:** Train forecasting model using Ray Train  
**Key Components:**
- Load historical data
- Preprocess data
- Set up Ray Train distributed training
- Train model (can use Ray Train or simple training)
- Evaluate model (MAE, RMSE, MAPE)
- Save model to `/app/models/forecasting/v{version}/`
- Save metadata (metrics, training date, etc.)

**Dependencies:**
- `data_loader.py`
- `model_factory.py`

---

#### 9. `src/ray/training/train_anomaly.py`
**Purpose:** Train anomaly detection model  
**Key Components:**
- Load historical data (including labeled anomalies if available)
- Preprocess data
- Train model (Isolation Forest, Autoencoder, or statistical)
- Evaluate model (Precision, Recall, F1-score)
- Save model to `/app/models/anomaly/v{version}/`
- Save metadata

**Dependencies:**
- `data_loader.py`
- `model_factory.py`

---

### Priority 3: Supporting Files

#### 10. `src/ray/inference/predictor.py` (Optional)
**Purpose:** Additional prediction utilities  
**Key Functions:**
- `format_prediction_result(forecast, anomaly_score, features)` - Format output
- `validate_features(features)` - Validate input features
- Helper functions for prediction logic

**Dependencies:** None (utility functions)

---

## Implementation Checklist

### Step 1: Basic Inference (Get Pipeline Working)
- [ ] Create `model_loader.py` with simple model loading
- [ ] Create `forecasting_model.py` with simple linear model
- [ ] Create `anomaly_model.py` with simple threshold-based detection
- [ ] Create `inference_actor.py` that loads models and performs inference
- [ ] Create `ray_consumer.py` that consumes from Kafka and uses actors
- [ ] Test: Verify data flows from `weather-features` → Ray → `weather-predictions`

### Step 2: Training Pipeline
- [ ] Create `data_loader.py` for loading historical data
- [ ] Create `model_factory.py` for creating models
- [ ] Create `train_forecasting.py` - train simple model first
- [ ] Create `train_anomaly.py` - train simple model first
- [ ] Test: Train models and verify they save correctly
- [ ] Update inference actors to load trained models

### Step 3: Improve Models
- [ ] Upgrade forecasting model (LSTM, Prophet, etc.)
- [ ] Upgrade anomaly model (Isolation Forest, Autoencoder)
- [ ] Add model versioning
- [ ] Add model evaluation metrics

---

## Quick Start: Minimal Viable Implementation

To get the pipeline working quickly, you can start with:

1. **Simple Models (No Training Needed Initially):**
   - Forecasting: Linear regression with simple trend
   - Anomaly: Statistical thresholds (e.g., temperature > 3 std devs from mean)

2. **Core Files (Minimum):**
   - `model_loader.py` - Can return simple models initially
   - `forecasting_model.py` - Simple linear prediction
   - `anomaly_model.py` - Simple threshold detection
   - `inference_actor.py` - Use simple models
   - `ray_consumer.py` - Main consumer

3. **Training Files (Can Add Later):**
   - Start with simple models, add training later
   - Or use pre-trained models from scikit-learn

---

## Data Flow

```
weather-features (Kafka)
    ↓
ray_consumer.py (consumes messages)
    ↓
inference_actor.py (Ray actor, performs ML inference)
    ↓
forecasting_model.py + anomaly_model.py (actual models)
    ↓
Formatted predictions
    ↓
weather-predictions (Kafka)
```

---

## Testing Strategy

1. **Unit Tests:**
   - Test model loading
   - Test inference actor with sample data
   - Test prediction formatting

2. **Integration Tests:**
   - Test: Kafka → Ray Consumer → Inference Actor → Kafka
   - Verify predictions appear in `weather-predictions` topic
   - Test with multiple stations

3. **End-to-End Test:**
   - Producer → Spark → Ray → Predictions
   - Measure latency
   - Verify predictions are reasonable

---

## Notes

- Start simple: Use basic models first, upgrade later
- Models can be saved as pickle files initially (simple)
- Ray actors should be long-lived (reuse across messages)
- Consider batch processing for efficiency
- Add error handling and logging throughout

