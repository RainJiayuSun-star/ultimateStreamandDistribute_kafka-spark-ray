# Model Training Guide: LSTM, Prophet, and XGBoost

## Overview

This document describes the roles, benefits, and training techniques for three complementary models used in our weather forecasting system: **LSTM**, **Prophet**, and **XGBoost**. Each model serves a distinct purpose and together they form a robust ensemble for weather prediction.

---

## Model Roles and Benefits

### 1. LSTM (Long Short-Term Memory) - Multivariate Sequence Learning

#### Role
- **Primary Function**: Learn complex temporal patterns and relationships between multiple weather variables
- **Best For**: Short to medium-term forecasting (1-24 hours ahead)
- **Strengths**: Captures non-linear relationships, handles multivariate inputs, learns from sequences

#### Key Benefits

1. **Multivariate Forecasting**
   - Can simultaneously use: temperature, humidity, pressure, wind speed, wind direction, precipitation
   - Learns how these variables interact (e.g., pressure drop + wind increase → storm approaching)
   - Captures complex weather system dynamics

2. **Sequence Learning**
   - Understands temporal dependencies (what happened hours/days ago affects future)
   - Learns diurnal patterns (day/night cycles)
   - Captures seasonal trends from historical sequences

3. **Non-Linear Pattern Recognition**
   - Identifies complex relationships that linear models miss
   - Handles sudden weather changes (cold fronts, storms)
   - Adapts to local weather patterns

#### When to Use LSTM
- ✅ Short-term forecasts (1-24 hours)
- ✅ When you have multiple weather variables
- ✅ When weather system dynamics matter (storms, fronts)
- ✅ Real-time inference with current conditions

#### Limitations
- ❌ Requires substantial training data (thousands of sequences)
- ❌ Computationally intensive (needs GPU for large models)
- ❌ Less interpretable than Prophet
- ❌ Sensitive to data quality issues

---

### 2. Prophet - Interpretable Long-Term Forecasting

#### Role
- **Primary Function**: Long-term seasonal forecasting with interpretable components
- **Best For**: Long-term forecasts (weeks to months ahead), seasonal planning
- **Strengths**: Interpretability, handles missing data, automatic seasonality detection

#### Key Benefits

1. **Interpretable Components**
   - Decomposes forecasts into: trend + yearly seasonality + weekly seasonality + holiday effects
   - Explains WHY a prediction was made (e.g., "28°F because it's December in Wisconsin")
   - Business-friendly explanations for stakeholders

2. **Robust to Missing Data**
   - Handles gaps in historical data gracefully
   - Works with irregular time series
   - Less sensitive to outliers than neural networks

3. **Automatic Seasonality Detection**
   - Automatically finds yearly patterns (winter/summer)
   - Detects weekly patterns if present
   - Handles multiple seasonalities simultaneously

4. **Long-Term Forecasting**
   - Excellent for seasonal planning (e.g., "What will temperature be on Dec 25, 2026?")
   - Learns from 29 years of historical data
   - Stable predictions for months ahead

#### When to Use Prophet
- ✅ Long-term forecasts (weeks/months ahead)
- ✅ When interpretability is important
- ✅ Seasonal planning and business forecasting
- ✅ When you only have temperature data (univariate)
- ✅ When you need to explain predictions to non-technical users

#### Limitations
- ❌ Primarily univariate (one variable at a time)
- ❌ Doesn't use current weather conditions (pressure, wind, etc.)
- ❌ Less accurate for short-term forecasts (< 24 hours)
- ❌ Can't capture sudden weather events (storms, fronts)

---

### 3. XGBoost - Fast Anomaly Detection and Real-Time Inference

#### Role
- **Primary Function**: Fast anomaly detection and real-time forecasting
- **Best For**: Anomaly detection, fast inference, handling missing features
- **Strengths**: Speed, flexibility, robustness to missing data

#### Key Benefits

1. **Extreme Speed**
   - CPU-only inference (no GPU needed)
   - Sub-millisecond predictions
   - Perfect for real-time streaming (Kafka → Ray → XGBoost)

2. **Anomaly Detection**
   - Catches sensor glitches instantly (e.g., temperature = 500°C)
   - Protects deep learning models from bad data
   - Acts as "speed layer" filter in Lambda Architecture

3. **Feature Flexibility**
   - Can train on one set of features, infer with different features
   - Handles missing features gracefully
   - Works with both historical and real-time data

4. **Robust to Data Issues**
   - Less sensitive to outliers than neural networks
   - Handles mixed data types (numeric + categorical)
   - Good with small datasets

#### When to Use XGBoost
- ✅ Real-time anomaly detection
- ✅ Fast inference requirements
- ✅ When features vary between training and inference
- ✅ CPU-only environments
- ✅ When you need quick baseline predictions

#### Limitations
- ❌ Less powerful for complex temporal patterns than LSTM
- ❌ Requires feature engineering (lag features, time features)
- ❌ Less interpretable than Prophet (but more than LSTM)
- ❌ May not capture long-term dependencies as well as LSTM

---

## Model Comparison Summary

| Aspect | LSTM | Prophet | XGBoost |
|--------|------|---------|---------|
| **Forecast Horizon** | 1-24 hours | Weeks/Months | 1-24 hours |
| **Input Variables** | Multiple (multivariate) | Single (univariate) | Multiple (flexible) |
| **Training Data** | Hourly sequences (8760+ hours) | Daily historical (29 years) | Both |
| **Inference Speed** | Medium (GPU recommended) | Fast (CPU) | Very Fast (CPU) |
| **Interpretability** | Low (black box) | High (decomposable) | Medium |
| **Missing Data** | Sensitive | Robust | Robust |
| **Use Case** | Short-term, complex dynamics | Long-term, seasonal | Anomaly detection, fast inference |

---

## Training Techniques

### Data Sources

Our training pipeline uses three data sources:

1. **Hourly Normals (2012)**: `src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv`
   - 8760 hours of climatological normals
   - Features: Temperature, Dewpoint, Wind Speed, Wind Direction
   - Use: Learn hourly patterns, diurnal cycles

2. **Daily Historical (1996-2025)**: `src/data/historical/madison1996_2025_combined_cleaned.csv`
   - 29 years of daily observations
   - Features: TMAX, TMIN, TAVG, AWND, PRCP
   - Use: Learn long-term trends, seasonal patterns

3. **Real-Time Stream (Kafka)**: Current weather conditions
   - Features: Temperature, Humidity, Pressure, Wind Speed, Wind Direction
   - Use: Real-time inference (not for training initially)

---

## Training Strategy: Hybrid Approach

### Stage 1: Pre-training on Hourly Normals (LSTM)

**Purpose**: Learn hourly patterns and diurnal cycles

```python
# Load hourly normals
data = load_hourly_normals('2012_hourly.csv')

# Features:
# - HLY-TEMP-NORMAL (temperature)
# - HLY-DEWP-NORMAL (dewpoint → humidity proxy)
# - HLY-WIND-AVGSPD (wind speed)
# - HLY-WIND-1STDIR (wind direction)
# - hour_of_day (0-23)
# - day_of_year (1-365)

# Train LSTM to learn:
# - Diurnal temperature patterns
# - Hourly wind patterns
# - Seasonal variations
```

**Benefits**:
- Learns fundamental hourly patterns
- Understands day/night cycles
- Captures typical weather behavior

**Limitations**:
- Normals don't capture actual weather events
- No pressure data (all values = 1.0)
- Represents typical conditions, not extremes

---

### Stage 2: Fine-tuning on Daily Historical (All Models)

**Purpose**: Learn long-term trends and seasonal patterns

```python
# Load daily historical data
data = load_daily_historical('1996_2025_combined_cleaned.csv')

# Features:
# - TMAX, TMIN, TAVG (temperature extremes)
# - AWND (average wind speed)
# - PRCP (precipitation)
# - day_of_year, month (time features)

# Train models to learn:
# - Long-term climate trends
# - Seasonal extremes
# - Precipitation patterns
```

**Benefits**:
- 29 years of real observations
- Captures actual weather variability
- Long-term climate understanding

**Limitations**:
- Daily resolution (no hourly detail)
- Missing pressure, humidity, detailed wind
- No real-time features

---

### Stage 3: Real-Time Inference

**Purpose**: Use current conditions for short-term forecasts

```python
# Get features from Kafka stream
features = {
    'temperature': 45.0,
    'humidity': 65.0,      # NEW - not in training
    'pressure': 1012.0,    # NEW - not in training
    'wind_speed': 8.0,
    'wind_direction': 230, # NEW - not in training
    'hour_of_day': 14,
    'day_of_year': 350
}

# Models can now use:
# - Pressure drops → storm approaching
# - Wind direction changes → weather system moving
# - High humidity + pressure drop → precipitation likely
```

**Note**: Models trained on historical data can still use new real-time features if the model architecture supports it (XGBoost handles this well, LSTM needs retraining).

---

## Training Procedures

### LSTM Training

#### Data Preparation

1. **Load and Combine Data**
   ```python
   # Load hourly normals
   hourly_data = pd.read_csv('2012_hourly.csv')
   
   # Load daily historical
   daily_data = pd.read_csv('1996_2025_combined_cleaned.csv')
   
   # Feature engineering
   hourly_data['hour'] = pd.to_datetime(hourly_data['DATE']).dt.hour
   hourly_data['day_of_year'] = pd.to_datetime(hourly_data['DATE']).dt.dayofyear
   ```

2. **Create Sequences**
   ```python
   # Create sliding windows for LSTM
   # Input: 24 hours of history
   # Output: Next 24 hours of temperature
   
   lookback = 24  # hours
   forecast_horizon = 24  # hours
   
   X, y = create_sequences(
       data=hourly_data,
       lookback=lookback,
       forecast_horizon=forecast_horizon,
       features=['temp', 'dewpoint', 'wind_speed', 'wind_dir']
   )
   ```

3. **Normalization**
   ```python
   from sklearn.preprocessing import StandardScaler
   
   scaler = StandardScaler()
   X_scaled = scaler.fit_transform(X)
   y_scaled = scaler.fit_transform(y)
   ```

#### Model Architecture

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(24, 4)),  # 24 timesteps, 4 features
    Dropout(0.2),
    LSTM(32, return_sequences=False),
    Dropout(0.2),
    Dense(24)  # Predict 24 hours ahead
])
```

#### Training

```python
model.compile(
    optimizer='adam',
    loss='mse',
    metrics=['mae']
)

history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=50,
    batch_size=32,
    callbacks=[EarlyStopping(patience=5)]
)
```

#### Evaluation Metrics

- **MAE** (Mean Absolute Error): Average prediction error in °F
- **RMSE** (Root Mean Squared Error): Penalizes large errors
- **MAPE** (Mean Absolute Percentage Error): Percentage error

---

### Prophet Training

#### Data Preparation

1. **Format for Prophet**
   ```python
   # Prophet requires specific format: 'ds' (date) and 'y' (target)
   prophet_data = pd.DataFrame({
       'ds': pd.to_datetime(daily_data['DATE']),
       'y': daily_data['TMAX']  # or TAVG, TMIN
   })
   ```

2. **Handle Missing Values**
   ```python
   # Prophet handles missing data, but we can interpolate
   prophet_data = prophet_data.interpolate()
   ```

#### Model Configuration

```python
from prophet import Prophet

model = Prophet(
    yearly_seasonality=True,      # Yearly patterns
    weekly_seasonality=True,       # Weekly patterns (if present)
    daily_seasonality=False,       # Daily (not needed for daily data)
    seasonality_mode='multiplicative',  # or 'additive'
    changepoint_prior_scale=0.05    # Flexibility
)
```

#### Training

```python
# Prophet training is simple
model.fit(prophet_data)

# Create future dataframe
future = model.make_future_dataframe(periods=365)  # 1 year ahead

# Predict
forecast = model.predict(future)
```

#### Evaluation

```python
# Cross-validation
from prophet.diagnostics import cross_validation, performance_metrics

df_cv = cross_validation(
    model,
    initial='730 days',  # 2 years training
    period='180 days',   # Retrain every 6 months
    horizon='90 days'    # Predict 90 days ahead
)

metrics = performance_metrics(df_cv)
# Returns: MAE, RMSE, MAPE, etc.
```

---

### XGBoost Training

#### Data Preparation

1. **Feature Engineering**
   ```python
   # Create time features
   data['hour'] = pd.to_datetime(data['DATE']).dt.hour
   data['day_of_year'] = pd.to_datetime(data['DATE']).dt.dayofyear
   data['month'] = pd.to_datetime(data['DATE']).dt.month
   data['day_of_week'] = pd.to_datetime(data['DATE']).dt.dayofweek
   
   # Create lag features
   data['temp_lag_1'] = data['TMAX'].shift(1)
   data['temp_lag_7'] = data['TMAX'].shift(7)
   data['temp_rolling_mean_7'] = data['TMAX'].rolling(7).mean()
   ```

2. **Prepare Features and Target**
   ```python
   features = [
       'TMAX', 'TMIN', 'AWND', 'PRCP',
       'hour', 'day_of_year', 'month',
       'temp_lag_1', 'temp_lag_7', 'temp_rolling_mean_7'
   ]
   
   X = data[features]
   y = data['TMAX'].shift(-1)  # Predict next day's max temp
   
   # Remove NaN rows
   X = X.dropna()
   y = y[X.index]
   ```

#### Model Configuration

```python
import xgboost as xgb

model = xgb.XGBRegressor(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42
)
```

#### Training

```python
# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, shuffle=False  # Don't shuffle time series!
)

# Train
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    early_stopping_rounds=10,
    verbose=True
)
```

#### Evaluation

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
```

---

## Model Ensemble Strategy

### Combining Predictions

```python
def ensemble_predict(lstm_pred, prophet_pred, xgboost_pred, weights=[0.4, 0.3, 0.3]):
    """
    Combine predictions from multiple models.
    
    Args:
        lstm_pred: LSTM prediction (short-term)
        prophet_pred: Prophet prediction (long-term)
        xgboost_pred: XGBoost prediction (fast baseline)
        weights: Weight for each model
    
    Returns:
        Ensemble prediction
    """
    # For short-term: Weight LSTM more
    if forecast_horizon <= 24:
        weights = [0.5, 0.2, 0.3]  # LSTM, Prophet, XGBoost
    
    # For long-term: Weight Prophet more
    elif forecast_horizon > 7:
        weights = [0.2, 0.6, 0.2]  # LSTM, Prophet, XGBoost
    
    return (weights[0] * lstm_pred + 
            weights[1] * prophet_pred + 
            weights[2] * xgboost_pred)
```

---

## Training Workflow

### Step-by-Step Process

1. **Data Preparation**
   ```bash
   python src/ray/training/data_loader.py
   ```

2. **Train LSTM**
   ```bash
   python src/ray/training/train_lstm.py \
       --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv \
       --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
       --epochs 50 \
       --batch-size 32
   ```

3. **Train Prophet**
   ```bash
   python src/ray/training/train_prophet.py \
       --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
       --target TMAX \
       --forecast-days 365
   ```

4. **Train XGBoost**
   ```bash
   python src/ray/training/train_xgboost.py \
       --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
       --n-estimators 100 \
       --max-depth 6
   ```

5. **Evaluate Models**
   ```bash
   python src/ray/training/evaluate_models.py \
       --model-dir /app/models
   ```

---

## Quick Start Examples

### 1. Quick LSTM Training (Recommended for RTX 4070 Mobile)

```bash
python src/ray/training/train_lstm.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --epochs 30 \
    --batch-size 64 \
    --use-gpu \
    --mixed-precision
```

### 2. Quick Prophet Training

```bash
python src/ray/training/train_prophet.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv
```

### 3. Quick XGBoost Training

```bash
python src/ray/training/train_xgboost.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv
```

---

## Common Issues and Solutions

### Issue 1: ModuleNotFoundError

**Solution**: Install missing package
```bash
pip install tensorflow prophet xgboost
```

### Issue 2: GPU Not Detected

**Check GPU availability**:
```bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

**If no GPU, use CPU**:
```bash
python src/ray/training/train_lstm.py --daily-data ... --no-gpu
```

### Issue 3: Out of Memory (OOM)

**Reduce batch size**:
```bash
python src/ray/training/train_lstm.py \
    --daily-data ... \
    --batch-size 16  # Instead of 32
```

### Issue 4: File Not Found

**Check file path (use absolute or relative path)**:
```bash
python src/ray/training/train_lstm.py \
    --daily-data ./src/data/historical/madison1996_2025_combined_cleaned.csv
```

---

## Model Output Location

Trained models are saved to:
```
/app/models/forecasting/v{version}/
├── model.h5 (LSTM) or model.pkl (Prophet/XGBoost)
├── feature_adapter.pkl
├── scaler_X.pkl (LSTM only)
├── scaler_y.pkl (LSTM only)
└── metadata.json
```

**Metadata includes**:
- Training date
- Model version
- Evaluation metrics (MAE, RMSE, MAPE)
- Feature list
- Training parameters

---

## Tips

1. **Start with XGBoost** (fastest, ~1-2 minutes)
2. **Then Prophet** (medium, ~5-10 minutes)
3. **Finally LSTM** (slowest, ~30-60 minutes with GPU)

4. **Monitor GPU usage**:
   ```bash
   # In another terminal
   watch -n 1 nvidia-smi
   ```

5. **Check training progress**:
   - LSTM shows epoch-by-epoch progress
   - XGBoost shows boosting rounds
   - Prophet shows training completion

6. **View saved metrics**:
   ```bash
   cat /app/models/forecasting/v*/metadata.json
   ```

---

## Example: Complete Training Workflow

```bash
# 1. Train XGBoost (fast baseline)
python src/ray/training/train_xgboost.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv

# 2. Train Prophet (long-term forecasts)
python src/ray/training/train_prophet.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --forecast-days 365

# 3. Train LSTM (best accuracy, needs GPU)
python src/ray/training/train_lstm.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --epochs 50 \
    --use-gpu \
    --mixed-precision
```

All models will be saved with feature adapters ready for inference on Spark-aggregated data.

---

## Best Practices

### 1. Data Quality
- ✅ Check for missing values
- ✅ Handle outliers appropriately
- ✅ Validate feature ranges (e.g., temperature -50°F to 120°F)
- ✅ Ensure consistent time zones

### 2. Train/Validation/Test Split
- ✅ Use time-based splitting (don't shuffle!)
- ✅ Reserve recent data for testing
- ✅ Use cross-validation for Prophet

### 3. Hyperparameter Tuning
- ✅ Use Ray Tune for automated search
- ✅ Start with default parameters
- ✅ Tune one parameter at a time

### 4. Model Monitoring
- ✅ Track prediction accuracy over time
- ✅ Retrain when performance degrades
- ✅ A/B test new models before full deployment

---

## Troubleshooting

### LSTM Not Learning
- Check data normalization
- Increase model capacity
- Verify sequences are correct
- Check for data leakage

### Prophet Overfitting
- Reduce `changepoint_prior_scale`
- Add regularization
- Use more historical data

### XGBoost Poor Performance
- Add more features (lag, rolling stats)
- Tune hyperparameters
- Check for missing values

---

## References

- [Prophet Documentation](https://facebook.github.io/prophet/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [LSTM for Time Series](https://www.tensorflow.org/tutorials/structured_data/time_series)
- [Ray Train Documentation](https://docs.ray.io/en/latest/train/train.html)

---


