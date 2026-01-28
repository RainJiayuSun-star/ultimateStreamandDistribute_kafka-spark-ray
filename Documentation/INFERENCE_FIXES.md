# Ray Inference Container Fixes and Unit Conversion Issues

**Date:** January 27, 2026  
**Status:** Fixed

## Issues Identified and Fixed

### 1. ✅ Ray Connection Issue (FIXED)

**Problem:**
The `ray-inference` container was failing to connect to the Ray cluster with error:
```
ValueError: Can't find a `node_ip_address.json` file from /tmp/ray/session_... 
for 60 seconds. A ray instance hasn't started.
```

**Root Cause:**
`ray.init(address="ray-head:6379")` from another container causes Ray to look for local session files (`node_ip_address.json`) as if starting a worker, instead of connecting as a pure client.

**Fix Applied (Ray Client):**
- **Ray head:** Start with `--ray-client-server-port=10001` so the Ray Client server listens on port 10001.
- **ray-inference:** Set `RAY_CLIENT_URL=ray://ray-head:10001` and connect via `ray.init(RAY_CLIENT_URL)`.
- Ray Client is intended for remote drivers; it avoids the `node_ip_address.json` issue.

**Files Changed:**
- `src/ray/inference/ray_consumer.py` – use Ray Client when `RAY_CLIENT_URL` is set; otherwise GCS address.
- `src/utils/config.py` – added `RAY_CLIENT_URL`.
- `docker-compose.yml` – ray-head `--ray-client-server-port=10001`; ray-inference `RAY_CLIENT_URL=ray://ray-head:10001`.

**Consequences if Broken:**
- **No predictions generated**: The `ray-inference` container is responsible for consuming features from `weather-features` topic and generating predictions
- **Pipeline incomplete**: Data flows: Producer → Spark → **STOPS HERE** (no predictions)
- **API has no data**: The API consumes from `weather-predictions` topic, which remains empty
- **Manual testing works**: The `test_ray_inference.py` script works because it runs directly and can connect, but the production container fails

---

### 2. ✅ Temperature Unit Mismatch (FIXED)

**Problem:**
- **Model trained on:** Celsius (metric) from hourly normals data
- **Producer sending:** Fahrenheit (imperial) - was converting Celsius to Fahrenheit
- **Result:** Model receives temperatures ~30-50°F higher than expected, causing incorrect predictions

**Example:**
- Actual temperature: 8.6°C (47.5°F)
- Producer was sending: 47.5°F (but model expects Celsius)
- Model interprets as: 47.5°C (117.5°F) - **completely wrong!**

**Fix Applied:**
- Removed Fahrenheit conversion in `producer.py`
- Now sends temperature directly in Celsius (metric)
- Added comments documenting that model expects metric units

**Files Changed:**
- `src/kafka_weather/producer.py` - Removed `temp_f` conversion, use `temperature` (Celsius)
- `src/ray/models/forecasting_model.py` - Added comments about metric units
- `src/testers/test_ray_inference.py` - Updated display to show both Celsius and Fahrenheit

**Impact:**
This was causing the model to make completely wrong predictions because it was receiving temperatures in the wrong scale. Predictions should now be accurate.

---

### 3. ✅ Wind Speed Units (VERIFIED)

**Status:** ✅ Already correct

- **NWS API returns:** Wind speed in m/s (metric)
- **Model trained on:** Wind speed in m/s (metric)
- **No conversion needed** - units already match

**Verification:**
- Training data: `HLY-WIND-AVGSPD` from hourly normals (m/s)
- Producer: `wind_speed` from NWS API (m/s)
- Model expects: `wind_speed` in m/s

---

### 4. ⚠️ Time Encoding - Model Does NOT Use Time Features

**Question:** Was the model trained with time encoding?

**Answer:** **NO** - The LSTM model does NOT use time features (hour, day_of_year, etc.)

**Evidence:**
1. **Model metadata** (`LSTM_FineTuned_20260124_193541/metadata.json`):
   ```json
   "features": ["temperature", "wind_speed", "dewpoint"]
   ```
   - Only 3 features: temperature, wind_speed, dewpoint
   - No time features included

2. **Training code** (`data_loader.py`):
   - Time features (hour, day_of_year, month, day_of_week) are extracted
   - But they are **only used for XGBoost models**, not LSTM
   - LSTM uses raw features only

3. **Inference code** (`forecasting_model.py`):
   - Only uses: temperature, wind_speed, dewpoint
   - No time features passed to model

**Why Temperatures Might Be Going Up at Night:**

The model was trained on hourly normals data, which should have daily patterns. However:

1. **No explicit time encoding**: The model doesn't know what hour of day it is
2. **Sequence-based learning**: The LSTM learns from sequences, but if all timesteps in the lookback window have similar values (repeated current features), it may not capture daily cycles well
3. **Current implementation**: The `_create_sequence_from_features()` method **repeats the current features** for all lookback timesteps, which means the model doesn't see a temporal sequence - it sees the same values repeated 7 times

**The Real Problem:**
```python
# In forecasting_model.py, line 136:
sequence = np.tile(feature_array, (self.lookback, 1))
```
This repeats the current features 7 times instead of using historical data. The model expects a sequence of different values over time, but gets the same value repeated.

**This explains why:**
- Predictions don't follow daily cycles
- Model can't learn "night = colder" because it doesn't see time information
- Predictions are based only on current conditions, not temporal patterns

**Potential Solutions (Future Work):**
1. Add time features to model input (hour, day_of_year with sin/cos encoding)
2. Use actual historical sequence instead of repeating current features
3. Retrain model with time-aware features

---

### 5. ✅ Recursive 24h Disabled (Unrealistic Jumps Fixed)

**Problem:**
When we extended forecasts to 24h by **recursively** running the 7h model (using predictions 1–7 as “history” for 8–14, etc.), temperatures jumped unrealistically: e.g. current -12°C → +8h ~20°C → +15h ~40°C → +22h ~55°C. Jumps occurred exactly at chunk boundaries (8, 15, 22).

**Root cause (inference, not the 7h model):**
1. **Synthetic “history” mismatch**: We fed our *predictions* for hours 1–7 as “past” for the next run. The model was trained on *real* past sequences, not predicted future values.
2. **Constant wind/dewpoint**: We kept current wind/dewpoint for all recursive steps; training had real temporal variation.
3. **Scaling extrapolation**: Predicted temps drifted (e.g. 25°C → 40°C); scaler saw out-of-range inputs and extrapolated.
4. **Compounding error**: Each recursive chunk amplified drift.

The **first 7 hours** (single forward pass) were plausible; the blow-up came from **recursive chaining**.

**Fix applied:**
- **Recursive 24h disabled.** We only run a **single** forward pass. If horizon > 7, we cap at 7 and log a warning.
- **`HORIZON_HOURS`** default set to **7** (config + docker-compose).
- Removed `_extract_wind_dewpoint` and `_build_sequence_from_temps` (recursive helpers).

**Files changed:** `forecasting_model.py`, `config.py`, `docker-compose.yml`, `ray_consumer.py`, `test_ray_inference.py`

**For 24h forecasts later:** Retrain a model with `forecast_horizon=24` so we get 24h in one forward pass, or feed real historical sequences instead of repeated/synthetic features.

---

## Summary of Fixes

### ✅ Fixed Issues:
1. **Ray connection** - ray-inference uses Ray Client (`ray://ray-head:10001`); ray-head runs with `--ray-client-server-port=10001`
2. **Temperature units** - Producer now sends Celsius (metric) instead of Fahrenheit
3. **Display units** - Test output shows both Celsius and Fahrenheit
4. **Unrealistic 24h jumps** - Recursive 24h disabled; we only predict 7h (single forward pass). `HORIZON_HOURS=7` default.

### ⚠️ Known Limitations:
1. **No time encoding** - Model doesn't use hour/day features
2. **Repeated features** - Model receives same values repeated instead of historical sequence
3. **Daily cycle not captured** - Model can't learn that temperatures drop at night
4. **7h horizon only** - 24h via recursion caused drift; use a horizon-24 model for 24h forecasts

### 📋 Next Steps (Future Improvements):
1. Add time features (hour, day_of_year) to model input with cyclic encoding
2. Use actual historical sequence from Spark instead of repeating current features
3. Consider retraining model with time-aware features for better daily cycle prediction

---

## Testing After Fixes

After applying these fixes:

1. **Recreate containers** (ray-head command and ray-inference env changed; `src` is mounted, no rebuild needed):
   ```bash
   docker compose down
   docker compose up -d
   ```
   If you use prebuilt images without mounts, rebuild:  
   `docker compose build ray-head ray-inference && docker compose up -d`

2. **Check Ray connection:**
   ```bash
   docker logs ray-inference | grep "Connected to Ray cluster"
   ```
   You should also see `Using Ray Client at ray://ray-head:10001` in ray-inference logs.

3. **Verify temperature units:**
   ```bash
   docker exec kafka python3 /app/src/testers/debug_consumer.py
   # Should show temperatures in Celsius (e.g., 8.6°C, not 47.5°F)
   ```

4. **Test inference:**
   ```bash
   docker exec ray-head python3 /app/src/testers/test_ray_inference.py
   # Should show predictions in Celsius with Fahrenheit conversion
   ```

---

## Model Training Details

**Model:** `LSTM_FineTuned_20260124_193541`

**Training Data:**
- Source: Hourly normals data (2012)
- Units: Metric (Celsius, m/s)
- Features: temperature, wind_speed, dewpoint
- Lookback: 7 hours
- Forecast horizon: 7 hours

**Expected Input:**
- Temperature: Celsius (not Fahrenheit)
- Wind speed: m/s (already correct)
- Dewpoint: Celsius (calculated from temperature and humidity)

**Expected Output:**
- Temperature predictions: Celsius (can be converted to Fahrenheit for display)
