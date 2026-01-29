# Implementation Design Document

## Overview
This project implements a Lambda Architecture (https://www.geeksforgeeks.org/system-design/what-is-lambda-architecture-system-design/#what-is-lambda-architecture) for real-time weather forecasting. It builds upon course project p7: Kafka, Weather Data. It integrates three distinct distributed system to leverage their respective strengths:
- Kafka: High-throughput data ingestion and decoupling
- Spark: Stateful stream processing and data parallelism (ETL)
- Ray: Low-latency logical parallelism for Machine Learning inference

The System ingests raw weather station data, aggregates it using a sliding window in Spark to reduce noise, and passes the aggregated features to a Ray cluster to detect anomalies and predict future trends in real-time.

## Deployment
Deployment will be done on a single VM via Docker Compose. The cluster will consists of the following 5 primary type of containers:

1. kafka: Single broker, acting as the central nervous system
2. spark-master: coordinator for the ETL pipeline
3. spark-worker: executes the heavy windowing/aggregation tasks.
4. ray-head: manages the ML actors and serves the Ray Dashboard
5. ray-worker: executes the training/inference actors.

### Commands:
To see the Topic Contents
#### Method 1: Use existing tester scripts
View weather-raw topic: 
```
# In Docker
docker exec -it kafka python3 /app/src/testers/debug_consumer.py

# Or locally (if Kafka accessible from host)
python3 src/testers/debug_consumer.py
```
---
View weather-feature topic: 
```
# In Docker
docker exec -it spark-master python3 /app/src/testers/test_spark_features.py

# Or locally
python3 src/testers/test_spark_features.py
```
---
View weather-predictions topic:
```
# In Docker
docker exec -it kafka python3 /app/src/testers/test_ray_predictions.py

# Or locally
python3 src/testers/test_ray_predictions.py
```

#### Method 2: Use Kafka console consumer (raw messages)
View messages from beginning
```
# weather-raw topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw \
  --from-beginning

# weather-features topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-features \
  --from-beginning

# weather-predictions topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-predictions \
  --from-beginning
```
View only new messages (latest):
```
# Remove --from-beginning flag
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw
```
View limited number of messages:
```
# View only 5 messages
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw \
  --from-beginning \
  --max-messages 5
```

## Communication Mechanisms

The system uses **Kafka as the sole communication mechanism** between components. All inter-service data flow goes through Kafka topics, providing decoupling, fault tolerance, and scalability.

### Multi-Topic Architecture

1. **Topic 1: `weather-raw`** (4 partitions)
   - **Producer**: Weather producer (`src/kafka_weather/producer.py`) — fetches from NWS API every 15 seconds.
   - **Consumer**: Spark Structured Streaming.
   - **Purpose**: Buffer raw incoming weather station data.
   - **Schema**: `station_id`, `station_name`, `timestamp`, `temperature`, `humidity`, `wind_speed`, `wind_direction`, `sea_level_pressure`, `precipitation_last_hour`, etc. (metric units: Celsius, m/s).

2. **Topic 2: `weather-features`** (4 partitions)
   - **Producer**: Spark Streaming (after 5-minute sliding-window aggregation).
   - **Consumer**: Ray inference consumer (`src/ray/inference/ray_consumer.py`).
   - **Purpose**: Decouple Spark processing from Ray inference.
   - **Schema**: `station_id`, `window_start`, `window_end`, aggregated features (mean, std, min, max per metric), measurement counts.

3. **Topic 3: `weather-predictions`** (4 partitions)
   - **Producer**: Ray inference actors (after LSTM forecasting).
   - **Consumer**: API (Flask) and dashboard frontend.
   - **Purpose**: Store prediction results for querying and visualization.
   - **Schema**: `station_id`, `station_name`, `timestamp`, `predictions` (e.g., temperature forecasts for next 7 hours), optional anomaly info, metadata.

### Consumer Groups

- **spark-streaming-group**: Spark consumes `weather-raw`.
- **ray-ml-inference**: Ray inference consumer consumes `weather-features`.
- **kafka-data-collector**: Saves raw data to JSONL files.
- **dashboard-consumers** (API): Consumes `weather-predictions` for REST endpoints.

### Benefits

- **Decoupling**: Components can be scaled, restarted, or updated independently.
- **Fault tolerance**: Data persists in Kafka; consumers can replay from offsets.
- **Backpressure**: Kafka buffers when downstream (e.g., Ray) is slow.
- **Multiple consumers**: Same topic can serve API, testers, and future analytics.

---

## System Design

### Lambda Architecture Layers

1. **Speed Layer (Real-time)**
   - **Ingestion**: NWS API → Producer → `weather-raw`.
   - **Processing**: Spark Structured Streaming — 5-minute sliding windows (1-minute slide), aggregations (mean, std, min, max), feature engineering.
   - **Inference**: Ray consumer reads `weather-features`, runs LSTM model in Ray actors, writes to `weather-predictions`.

2. **Batch Layer (Training)**
   - Historical data (e.g., NOAA hourly normals) → Ray training scripts → LSTM (and other) models.
   - Models saved under `models/trained/forecasting/` (e.g., `LSTM_FineTuned_20260124_193541`).
   - Inference loads these artifacts; no direct coupling between training and real-time pipeline beyond model files.

3. **Serving Layer**
   - API (Flask) reads from `weather-predictions` (and optionally other topics) to serve REST endpoints.
   - Frontend (React + TypeScript) calls the API and displays dashboards, maps, and time-series charts.

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Kafka** | Message broker; three topics; 4 partitions each; single broker (KRaft). |
| **Producer** | Fetch NWS data for 5 stations (KMSN, KMKE, KMDW, KMSP, KDSM); publish to `weather-raw`. |
| **Spark** | Consume `weather-raw`, window/aggregate, publish `weather-features`; checkpointing for fault tolerance. |
| **Ray** | Consume `weather-features`, run LSTM inference (7-hour horizon), publish `weather-predictions`; Ray Client used from inference container to Ray head. |
| **API** | Expose REST endpoints; read from Kafka topics (especially `weather-predictions`) to serve latest/recent data. |
| **Frontend** | React dashboard; calls API; visualizes stations, predictions, pipeline status. |

### Deployment Topology

- **Single host**: All services run via Docker Compose on one machine.
- **Containers**: Kafka (broker + producer), Kafka data collector, Spark master, 4 Spark workers, Spark streaming app, Ray head, 4 Ray workers, Ray inference consumer, API — 14 containers total.
- **Network**: Shared Docker network (`weather-network`); Kafka bootstrap `kafka:9092`; Ray Client `ray://ray-head:10001`.

---

## Client Interface

### REST API (Flask)

Base URL: `http://localhost:5000` (or API container host in Docker). All responses JSON; CORS enabled for frontend.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check; returns `{"status": "healthy", "service": "weather-api"}`. |
| `/predictions/latest` | GET | Latest prediction per partition from `weather-predictions`. |
| `/predictions` | GET | Recent predictions; query param `limit` (default 10). |
| `/topics/weather-raw` | GET | Recent messages from `weather-raw` by partition; optional `limit`. |
| `/topics/weather-features` | GET | Recent messages from `weather-features` by partition. |
| `/topics/weather-predictions` | GET | Recent messages from `weather-predictions` by partition. |
| `/stations/all` | GET | Aggregated view of raw, features, and predictions for all stations (last N messages per topic). |

Errors return appropriate HTTP status (e.g., 404 when topic or data unavailable, 500 on server errors) with an `error` message in the body.

### Frontend Dashboard (React + TypeScript)

- **Location**: `frontend/` (Vite, React, TypeScript).
- **Run**: `npm install && npm run dev`; typically `http://localhost:5173`.
- **Features**: Uses the REST API (e.g., `VITE_API_URL` or `http://localhost:5000`) for:
  - **Health**: System health and pipeline status.
  - **Predictions**: Latest and recent predictions; time-series charts (Recharts).
  - **Stations**: Map (Leaflet) and list of stations with raw, features, and predictions.
  - **Topics**: Inspect `weather-raw`, `weather-features`, `weather-predictions` by partition.
- **API service**: `frontend/src/services/api.ts` — axios client for all above endpoints.

### Programmatic Access

Any HTTP client can call the REST API. The frontend and test scripts (e.g., `debug_consumer.py`, `test_spark_features.py`, `test_ray_predictions.py`) are the primary clients; the API does not require authentication in the current design.

---

## Evaluation & Performance

### System Performance

- **End-to-end latency**: From raw observation to prediction in `weather-predictions`. Influenced by producer interval (15 s), Spark trigger/window, and Ray inference. Target: on the order of 1–2 minutes under normal load.
- **Throughput**: Producer emits 5 stations × 1 message per 15 s; Spark and Ray are sized (4 workers each) to handle this and moderate spikes.
- **Availability**: Health checks and restart policies in Docker Compose; Spark checkpointing and Kafka retention allow recovery from failures.
- **Scalability**: Horizontal scaling by adding Spark/Ray workers and partition count; Kafka partition count (4) and consumer groups support parallelism.

### ML Model Performance

- **Forecasting**: LSTM model (`LSTM_FineTuned_20260124_193541`) — metrics (from training/benchmark) can include MAE, RMSE, MAPE on validation/holdout data. Forecast horizon: 7 hours (single forward pass).
- **Inference latency**: Ray actors run on CPU; target sub-second per message; batch processing in the consumer improves throughput.
- **Anomaly detection**: Deferred; no anomaly model in production yet; future work to define precision/recall/F1 and thresholds.

### Operational Monitoring

- **Spark Master UI**: `http://localhost:8080` — jobs, stages, executors.
- **Ray Dashboard**: `http://localhost:8265` — actors, tasks, resources.
- **Logs**: `docker compose logs -f [service]` for debugging; API and Ray inference logs are especially useful for pipeline and model issues.
- **Testers**: `debug_consumer.py`, `test_spark_features.py`, `test_ray_predictions.py` validate each stage of the pipeline.

### Known Limitations

- Model uses current-window features only (no historical sequence from stream; no time-of-day encoding), which limits daily-cycle accuracy.
- Forecast horizon fixed at 7 hours; 24-hour forecasting would require a different or retrained model.
- Anomaly detection and dedicated `/anomalies` (or similar) endpoint are not yet implemented.

---

## Data or Dataset

### Real-Time Data (Speed Layer)

- **Source**: [NWS API](https://api.weather.gov/) (National Weather Service).
- **Method**: HTTP requests from the producer to NWS endpoints for 5 stations: KMSN (Madison), KMKE (Milwaukee), KMDW (Chicago), KMSP (Minneapolis), KDSM (Des Moines).
- **Frequency**: Every 15 seconds per run.
- **Units**: Metric — temperature in Celsius, wind speed in m/s, pressure in hPa, etc., to match the trained LSTM model.
- **Persistence**: Raw data is also saved to JSONL files by the Kafka data collector (`src/data/kafka_streaming/`).

### Historical Data (Batch Layer / Training)

- **Source**: NOAA datasets (e.g., hourly normals, station data). Can be downloaded from NOAA or other providers; see `exampleScript/` and `src/ray/training/` for data loading and training scripts.
- **Usage**: Train LSTM (and other) models; store under `models/trained/forecasting/` with metadata, scalers, and feature adapters.
- **Format**: Depends on the training script (e.g., CSV/Parquet); training code in `src/ray/training/` (e.g., `data_loader.py`, `train_lstm.py`, `finetune_lstm_hourly.py`).

### Data Schema Alignment

- Producer and Spark output schema must match what the Ray model expects (e.g., temperature, wind_speed, dewpoint in metric units). Feature adapter in `src/ray/models/` maps Spark-aggregated features to the model input format; see `forecasting_model.py` and model metadata under `models/trained/forecasting/`.
