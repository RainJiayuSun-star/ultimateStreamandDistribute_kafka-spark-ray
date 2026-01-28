# Guide to Improving Model Performance

This guide provides actionable strategies to improve the performance of LSTM, XGBoost, and Prophet models for weather forecasting.

## Current Performance Baseline

| Model | Test MAE | Test RMSE | Status |
|-------|----------|-----------|--------|
| **XGBoost** | 3.10°F | 4.02°F | ⭐ Best accuracy |
| **LSTM** | 3.84°F | 4.98°F | ⭐ Best generalization |
| **Prophet** | 6.80°F | 8.49°F | ⭐ Best for long-term |

---

## 1. XGBoost Improvements

### A. Hyperparameter Tuning

**Current Defaults:**
- `n_estimators=100`
- `max_depth=6`
- `learning_rate=0.1`
- `subsample=0.8`
- `colsample_bytree=0.8`

**Recommended Improvements:**

```python
# Option 1: More conservative (better generalization)
n_estimators=200,      # Increase from 100
max_depth=4,          # Decrease from 6 (reduce overfitting)
learning_rate=0.05,   # Decrease from 0.1 (more stable)
subsample=0.85,       # Slight increase
colsample_bytree=0.85,
min_child_weight=3,   # NEW: Add regularization
reg_alpha=0.1,        # NEW: L1 regularization
reg_lambda=1.0        # NEW: L2 regularization

# Option 2: More aggressive (better accuracy, risk of overfitting)
n_estimators=300,
max_depth=8,
learning_rate=0.03,
subsample=0.9,
colsample_bytree=0.9
```

**Implementation:** Add these parameters to `train_xgboost.py` and use grid search or Bayesian optimization.

### B. Enhanced Feature Engineering

**Current Features:**
- Lag features (1, 3, 7 days)
- Rolling statistics (7-day mean, std)
- Time features (year, month, day_of_year, day_of_week)

**Additional Features to Add:**

```python
# 1. Extended lag features
for lag in [1, 2, 3, 5, 7, 14, 21, 30]:  # More lags
    df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)

# 2. Multiple rolling windows
for window in [3, 7, 14, 30]:  # Different window sizes
    df[f'{target_col}_rolling_mean_{window}'] = df[target_col].rolling(window).mean()
    df[f'{target_col}_rolling_std_{window}'] = df[target_col].rolling(window).std()
    df[f'{target_col}_rolling_min_{window}'] = df[target_col].rolling(window).min()
    df[f'{target_col}_rolling_max_{window}'] = df[target_col].rolling(window).max()

# 3. Seasonal features
df['sin_month'] = np.sin(2 * np.pi * df['month'] / 12)
df['cos_month'] = np.cos(2 * np.pi * df['month'] / 12)
df['sin_day_of_year'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
df['cos_day_of_year'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)

# 4. Interaction features
df['temp_range'] = df['temp_max'] - df['temp_min']
df['temp_avg'] = (df['temp_max'] + df['temp_min']) / 2
df['precipitation_binary'] = (df['precipitation'] > 0).astype(int)

# 5. Weather regime features
df['is_winter'] = df['month'].isin([12, 1, 2]).astype(int)
df['is_summer'] = df['month'].isin([6, 7, 8]).astype(int)
df['is_spring'] = df['month'].isin([3, 4, 5]).astype(int)
df['is_fall'] = df['month'].isin([9, 10, 11]).astype(int)

# 6. Cross-feature interactions
df['wind_temp_interaction'] = df['wind_avg'] * df['temperature']
df['precip_temp_interaction'] = df['precipitation'] * df['temperature']
```

### C. Data Quality Improvements

1. **Handle Missing Values Better:**
   - Use forward fill for short gaps
   - Use seasonal averages for longer gaps
   - Flag missing data as a feature

2. **Outlier Detection:**
   - Remove or cap extreme values (e.g., temperature > 120°F or < -50°F)
   - Use IQR method for outlier detection

3. **Feature Selection:**
   - Use XGBoost's built-in feature importance
   - Remove low-importance features to reduce noise
   - Use recursive feature elimination

### D. Advanced Techniques

1. **Early Stopping with Validation:**
   - Monitor validation loss
   - Stop when validation doesn't improve for N rounds
   - Save best model checkpoint

2. **Cross-Validation:**
   - Use time-series cross-validation (walk-forward)
   - Train on multiple time windows

3. **Ensemble Methods:**
   - Train multiple XGBoost models with different seeds
   - Average predictions (reduces variance)

---

## 2. LSTM Improvements

### A. Architecture Enhancements

**Current Architecture:**
- 2 LSTM layers, 64 units each
- Dropout: 0.2
- Lookback: 7 days
- Forecast horizon: 7 days

**Recommended Improvements:**

```python
# Option 1: Deeper network (more capacity)
num_layers=3,          # Increase from 2
lstm_units=128,        # Increase from 64
dropout_rate=0.3,     # Increase from 0.2 (more regularization)

# Option 2: Bidirectional LSTM (captures past and future context)
# Use Bidirectional(LSTM(...)) wrapper

# Option 3: Attention mechanism
# Add attention layer after LSTM to focus on important time steps
```

### B. Hyperparameter Tuning

```python
# Learning rate scheduling
learning_rate=0.001,   # Start with 0.001
# Use ReduceLROnPlateau callback

# Batch size optimization
batch_size=64,         # Try 32, 64, 128

# Lookback window
lookback=14,           # Try 7, 14, 21, 30 days

# Forecast horizon
forecast_horizon=1,    # Start with 1-day ahead, then extend
```

### C. Feature Engineering for LSTM

**Current Features:**
- temperature, wind_avg, precipitation

**Additional Features:**

```python
# 1. More weather variables
features = [
    'temperature', 'temp_max', 'temp_min', 'temp_avg',
    'humidity', 'pressure', 'wind_speed', 'wind_direction',
    'precipitation', 'dew_point'
]

# 2. Normalized features (already done, but ensure consistency)
# Use StandardScaler or MinMaxScaler

# 3. Feature selection
# Use correlation analysis to remove redundant features
```

### D. Training Improvements

1. **Better Callbacks:**
   ```python
   callbacks = [
       EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
       ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5),
       ModelCheckpoint('best_model.h5', save_best_only=True)
   ]
   ```

2. **Data Augmentation:**
   - Add noise to training data (small random perturbations)
   - Time warping (slight time shifts)

3. **Sequence Length Optimization:**
   - Try different lookback windows: 7, 14, 21, 30 days
   - Use validation to find optimal length

4. **Multi-step Forecasting:**
   - Train separate models for different forecast horizons
   - Or use encoder-decoder architecture

### E. Advanced Architectures

1. **Temporal Convolutional Networks (TCN):**
   - Can be faster and sometimes better than LSTM
   - Better parallelization

2. **Transformer-based Models:**
   - Temporal Fusion Transformer (TFT)
   - Better attention to important time steps

3. **Hybrid Models:**
   - CNN-LSTM (convolutional layers + LSTM)
   - Better feature extraction

---

## 3. Prophet Improvements

### A. Hyperparameter Tuning

**Current Defaults:**
- `yearly_seasonality=True`
- `weekly_seasonality=True`
- `changepoint_prior_scale=0.05`
- `seasonality_mode='multiplicative'`

**Recommended Improvements:**

```python
# Option 1: More flexible trend
changepoint_prior_scale=0.1,  # Increase from 0.05 (more changepoints)
n_changepoints=25,            # Explicit number of changepoints

# Option 2: Better seasonality
yearly_seasonality=10,        # Use Fourier order 10 (more flexible)
weekly_seasonality=3,         # Use Fourier order 3
daily_seasonality=False,      # Keep False for daily data

# Option 3: Add custom seasonalities
# For example, monthly patterns
model.add_seasonality(name='monthly', period=30.5, fourier_order=5)

# Option 4: Seasonality mode
seasonality_mode='additive',  # Try 'additive' vs 'multiplicative'
```

### B. Adding Regressors

**Current:** Univariate (only target variable)

**Improvement:** Add external regressors

```python
# Add weather features as regressors
model.add_regressor('precipitation')
model.add_regressor('wind_avg')
model.add_regressor('humidity')
model.add_regressor('pressure')

# Prepare data with regressors
prophet_data = pd.DataFrame({
    'ds': dates,
    'y': target,
    'precipitation': precipitation,
    'wind_avg': wind_avg,
    'humidity': humidity,
    'pressure': pressure
})
```

### C. Handling Outliers and Anomalies

```python
# 1. Identify outliers
outliers = (prophet_data['y'] < lower_bound) | (prophet_data['y'] > upper_bound)
prophet_data.loc[outliers, 'y'] = np.nan  # Prophet handles NaN

# 2. Use holidays/events
# Add known events that affect weather (e.g., El Niño years)
model.add_country_holidays(country_name='US')
```

### D. Uncertainty Intervals

```python
# Adjust uncertainty intervals
model = Prophet(
    interval_width=0.95,  # 95% confidence interval (default 0.8)
    mcmc_samples=300      # For better uncertainty estimates
)
```

---

## 4. General Improvements (All Models)

### A. Data Quality

1. **Data Cleaning:**
   - Remove duplicates
   - Handle missing values systematically
   - Detect and handle outliers
   - Validate data ranges (e.g., temperature in reasonable bounds)

2. **Feature Engineering:**
   - Create domain-specific features
   - Growing degree days
   - Heating/cooling degree days
   - Weather indices

3. **External Data Sources:**
   - Add weather station metadata
   - Include geographic features (latitude, longitude, elevation)
   - Add climate indices (El Niño, La Niña)

### B. Model Selection Strategy

1. **Use Different Models for Different Horizons:**
   - **1-3 days:** XGBoost (best accuracy)
   - **4-14 days:** LSTM (sequence patterns)
   - **15+ days:** Prophet (long-term trends)

2. **Ensemble Methods:**
   ```python
   # Weighted average ensemble
   prediction = (
       0.5 * xgboost_prediction +
       0.3 * lstm_prediction +
       0.2 * prophet_prediction
   )
   
   # Or use stacking
   # Train meta-learner on predictions from base models
   ```

### C. Evaluation Improvements

1. **Better Metrics:**
   - Add directional accuracy (did temperature go up/down correctly?)
   - Add quantile loss for uncertainty
   - Use domain-specific metrics (e.g., forecast skill score)

2. **Time-Series Cross-Validation:**
   - Use walk-forward validation
   - Test on multiple time periods
   - Ensure no data leakage

### D. Production Considerations

1. **Model Monitoring:**
   - Track prediction accuracy over time
   - Detect model drift
   - Retrain periodically (e.g., monthly)

2. **A/B Testing:**
   - Compare new models with current production model
   - Gradual rollout

---

## 5. Quick Wins (Easy to Implement)

### Priority 1: Immediate Impact

1. **XGBoost:**
   - Add regularization (reg_alpha, reg_lambda)
   - Increase n_estimators to 200-300
   - Add more lag features (14, 21, 30 days)

2. **LSTM:**
   - Add ReduceLROnPlateau callback
   - Increase lookback to 14 days
   - Add more features (humidity, pressure)

3. **Prophet:**
   - Add external regressors (precipitation, wind)
   - Tune changepoint_prior_scale
   - Add custom seasonalities

### Priority 2: Medium Effort

1. **Feature Engineering:**
   - Add seasonal features (sin/cos of month, day_of_year)
   - Add interaction features
   - Add rolling statistics with multiple windows

2. **Hyperparameter Tuning:**
   - Use grid search or random search
   - Use Bayesian optimization (Optuna, Hyperopt)

### Priority 3: Advanced

1. **Ensemble Methods:**
   - Combine predictions from all three models
   - Use stacking with meta-learner

2. **Advanced Architectures:**
   - Try Transformer models
   - Try Temporal Fusion Transformer (TFT)

---

## 6. Implementation Roadmap

### Week 1: Quick Wins
- [ ] Add regularization to XGBoost
- [ ] Increase XGBoost n_estimators
- [ ] Add more lag features
- [ ] Add seasonal features (sin/cos)

### Week 2: Feature Engineering
- [ ] Add multiple rolling windows
- [ ] Add interaction features
- [ ] Add weather regime features
- [ ] Feature selection based on importance

### Week 3: Hyperparameter Tuning
- [ ] Set up hyperparameter search framework
- [ ] Tune XGBoost hyperparameters
- [ ] Tune LSTM architecture
- [ ] Tune Prophet parameters

### Week 4: Advanced Techniques
- [ ] Implement ensemble method
- [ ] Add external data sources
- [ ] Set up model monitoring
- [ ] A/B testing framework

---

## 7. Expected Improvements

Based on these improvements, you can expect:

| Model | Current Test MAE | Expected Test MAE | Improvement |
|-------|------------------|-------------------|-------------|
| **XGBoost** | 3.10°F | **2.5-2.8°F** | 10-20% |
| **LSTM** | 3.84°F | **3.0-3.3°F** | 15-22% |
| **Prophet** | 6.80°F | **5.5-6.0°F** | 12-19% |
| **Ensemble** | - | **2.2-2.5°F** | Best of all |

---

## 8. Tools and Libraries

- **Hyperparameter Tuning:**
  - Optuna (Bayesian optimization)
  - Hyperopt
  - scikit-learn GridSearchCV

- **Feature Engineering:**
  - tsfresh (automatic feature extraction)
  - Feature-engine

- **Model Evaluation:**
  - scikit-learn metrics
  - Custom time-series metrics

- **Ensemble:**
  - scikit-learn StackingRegressor
  - Custom weighted averaging

---

## Next Steps

1. Start with **Priority 1** quick wins
2. Measure baseline performance
3. Implement improvements one at a time
4. Compare results after each change
5. Document what works best for your data

Remember: **Not all improvements will work for every dataset.** Test systematically and keep what improves performance.

