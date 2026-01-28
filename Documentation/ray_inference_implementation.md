# Ray ML Inference Pipeline Implementation

## Overview

This document describes the implementation of Phase 1: ML Inference Pipeline for the weather forecasting system. The pipeline consumes aggregated features from Kafka, performs LSTM-based temperature forecasting using Ray actors, and publishes predictions back to Kafka.

## Architecture

### Components

1. **Model Loader** (`src/ray/models/model_loader.py`)
   - Loads LSTM model from `/app/models/trained/forecasting/LSTM_FineTuned_20260124_193541/`
   - Loads scalers (scaler_X.pkl, scaler_y.pkl)
   - Loads feature adapter for Spark feature conversion
   - Loads model metadata

2. **Forecasting Model** (`src/ray/models/forecasting_model.py`)
   - Wrapper class for LSTM model
   - Handles feature preprocessing and adaptation
   - Generates temperature predictions (short-term and long-term)
   - Supports 6-24+ hour forecast horizons

3. **Inference Actor** (`src/ray/inference/inference_actor.py`)
   - Ray remote actor with fractional GPU support (0.25 GPU per actor)
   - Loads models once on initialization
   - Handles inference requests asynchronously
   - Supports batch processing

4. **Ray Consumer** (`src/ray/inference/ray_consumer.py`)
   - Kafka consumer for `weather-features` topic
   - Creates and manages Ray inference actors
   - Processes messages and generates predictions
   - Publishes to `weather-predictions` topic

## GPU Configuration

### Fractional GPU Allocation

The system uses **fractional GPU allocation** to share a single RTX 4070 mobile GPU across multiple Ray actors:

- **4 Ray inference actors** each request `0.25 GPU` (total = 1.0 GPU)
- Ray automatically manages GPU memory sharing
- Each actor can run inference in parallel on the same GPU

### Docker Configuration

All Ray containers (head and workers) are configured with GPU access:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

**Note:** Requires Docker with NVIDIA Container Toolkit installed.

## Data Flow

```
weather-features (Kafka)
    ↓
Ray Consumer (ray-inference container)
    ↓
Ray Inference Actors (4 actors, 0.25 GPU each)
    ├─→ Actor 1 → LSTM Model → Predictions
    ├─→ Actor 2 → LSTM Model → Predictions
    ├─→ Actor 3 → LSTM Model → Predictions
    └─→ Actor 4 → LSTM Model → Predictions
    ↓
Combined Predictions
    ↓
weather-predictions (Kafka)
```

## Model Details

### Model Information
- **Model Name:** `LSTM_FineTuned_20260124_193541`
- **Type:** LSTM (Long Short-Term Memory)
- **Lookback:** 7 timesteps
- **Forecast Horizon:** 7 timesteps (configurable)
- **Features:** temperature, wind_speed, dewpoint
- **Target:** temperature

### Model Files
Located in `/app/models/trained/forecasting/LSTM_FineTuned_20260124_193541/`:
- `model.h5` - Keras LSTM model
- `scaler_X.pkl` - Feature scaler
- `scaler_y.pkl` - Target scaler
- `feature_adapter.pkl` - Feature adapter for Spark features
- `metadata.json` - Model metadata

## Usage

### Starting the Pipeline

The Ray inference consumer starts automatically with Docker Compose:

```bash
docker compose up -d
```

The `ray-inference` container will:
1. Wait 30 seconds for dependencies (Ray cluster, Kafka)
2. Connect to Ray cluster at `ray-head:6379`
3. Create 4 inference actors
4. Start consuming from `weather-features` topic
5. Publish predictions to `weather-predictions` topic

### Manual Execution

To run the consumer manually:

```bash
# In Ray head or worker container
docker exec -it ray-head python3 /app/src/ray/inference/ray_consumer.py

# Or with custom options
docker exec -it ray-head python3 /app/src/ray/inference/ray_consumer.py \
  --model-name LSTM_FineTuned_20260124_193541 \
  --num-actors 4 \
  --no-gpu  # Disable GPU if needed
```

### Checking Status

```bash
# Check if consumer is running
docker ps | grep ray-inference

# Check logs
docker logs ray-inference

# Check Ray dashboard
# Open http://localhost:8265 in browser

# Check if predictions are being published
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \
  kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic weather-predictions
```

### Testing Predictions

Use the test consumer to see predictions:

```bash
docker exec -it ray-head python3 /app/src/testers/test_ray_predictions.py
```

## Configuration

### Environment Variables

- `RAY_HEAD_ADDRESS` - Ray cluster address (default: `ray-head:6379`)
- `MODEL_STORAGE_PATH` - Path to models (default: `/app/models`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

### Kafka Configuration

- **Input Topic:** `weather-features` (4 partitions)
- **Output Topic:** `weather-predictions` (4 partitions)
- **Consumer Group:** `ray-ml-inference`
- **Bootstrap Servers:** `kafka:9092`

## Performance Considerations

### Resource Usage

- **Ray Actors:** 4 actors × 0.25 GPU = 1.0 GPU total
- **Memory:** ~500MB per actor (model + inference)
- **CPU:** 1 CPU core per actor (shared with Ray workers)

### Throughput

- **Expected:** 10-50 predictions/second (depending on model complexity)
- **Latency:** 50-200ms per prediction (with GPU)
- **Batch Processing:** Supported for higher throughput

### Scaling

To scale inference:
1. Increase `--num-actors` in `ray_consumer.py`
2. Adjust fractional GPU allocation (e.g., 0.2 GPU per actor for 5 actors)
3. Add more Ray workers if CPU-bound

## Troubleshooting

### Model Not Found

```
FileNotFoundError: Model directory not found
```

**Solution:** Verify model exists at `/app/models/trained/forecasting/LSTM_FineTuned_20260124_193541/`

### GPU Not Available

```
No GPU devices found, using CPU
```

**Solution:** 
1. Verify NVIDIA Container Toolkit is installed
2. Check `nvidia-smi` shows GPU
3. Verify Docker GPU access: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

### Ray Connection Failed

```
Failed to connect to Ray cluster
```

**Solution:**
1. Check Ray head is running: `docker ps | grep ray-head`
2. Verify network connectivity: `docker exec ray-inference ping ray-head`
3. Check Ray logs: `docker logs ray-head`

### Kafka Connection Failed

```
Failed to initialize Kafka
```

**Solution:**
1. Check Kafka is running: `docker ps | grep kafka`
2. Verify Kafka is healthy: `docker exec kafka netstat -tuln | grep 9092`
3. Check Kafka logs: `docker logs kafka`

### Import Errors

```
ModuleNotFoundError: No module named 'ray.models'
```

**Solution:**
1. Verify `/app/src` is mounted correctly
2. Check `__init__.py` files exist in `src/ray/models/` and `src/ray/inference/`
3. Verify Python path: `docker exec ray-inference python3 -c "import sys; print(sys.path)"`

## Future Enhancements

1. **Anomaly Detection:** Add anomaly detection model (deferred to future phase)
2. **Model Versioning:** Support multiple model versions and A/B testing
3. **Batch Optimization:** Improve batch processing for higher throughput
4. **Monitoring:** Add metrics collection and performance monitoring
5. **Error Recovery:** Enhanced error handling and automatic recovery

## Files Created

- `src/ray/models/model_loader.py` - Model loading utilities
- `src/ray/models/forecasting_model.py` - Forecasting model wrapper
- `src/ray/models/__init__.py` - Models package init
- `src/ray/inference/inference_actor.py` - Ray inference actor
- `src/ray/inference/ray_consumer.py` - Kafka consumer
- `src/ray/inference/__init__.py` - Inference package init
- `docker-compose.yml` - Updated with GPU support and ray-inference container

