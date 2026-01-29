# Ultimate Stream and Distribute

UW Madison Fall 2025 Big Data System (CS544) final independent honors project. A Lambda Architecture-based real-time weather forecasting system integrating Kafka, Spark, and Ray for distributed stream processing and ML inference.
- Website: https://rainjiayusun-star.github.io/ultimateStreamandDistribute_kafka-spark-ray/
- Demo: https://youtu.be/O7TBcRkUm0E
## Purpose

After learning several well-known distributed systems from the course, I'm interested to see the outcome when I combine multiple of them. This project demonstrates a general-purpose multi-distributed system architecture for real-time stream processing and ML inference. 

It now serves for real-time weather forecasting system. It ingests real-time weather data from multiple stations, processes it through Spark streaming for feature aggregation, and performs ML inference using Ray for forecasting and potentially anomaly detection. While implemented for weather forecasting, the same architecture pattern can be applied to other domains such as:
- **Financial markets**: Stock price prediction, trading signal generation, fraud detection
- **IoT sensor networks**: Industrial monitoring, predictive maintenance, anomaly detection
- **E-commerce**: Real-time recommendation systems, demand forecasting, inventory optimization
- **Network security**: Intrusion detection, traffic analysis, threat prediction
- **Healthcare**: Patient monitoring, predictive analytics, medical device data processing

The core architecture (Kafka → Spark → Ray → API) remains the same; only the data sources, feature engineering, and ML models need to be adapted for each use case.

## Current Status

**✅ System is fully operational end-to-end**

The pipeline successfully processes real-time weather data from 5 stations and generates 7-hour temperature forecasts using a trained LSTM model. All core components are implemented and working:

- ✅ Data ingestion (Kafka Producer)
- ✅ Stream processing (Spark Streaming)
- ✅ ML inference (Ray with LSTM model)
- ✅ REST API (Flask endpoints)
- ✅ Frontend dashboard (React + TypeScript)

See [Project Status](#project-status) section below for detailed component status and known limitations.

## Quick Start

To start the processing, use docker
```bash
# Build all the images
docker compose build

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Access Points:**
- Spark Master UI: http://localhost:8080
- Ray Dashboard: http://localhost:8265
- API: http://localhost:5000

After the docker is running, you can open dashboard to view system status and messages
```bash
# to go to frontend directory, 
cd frontend
# run
npm install
npm run dev
```
The frontend will be available at `http://localhost:3000`

## Project Structure

```
├── src/
│   ├── kafka_weather/      # Kafka producer and data collector
│   ├── spark/               # Spark streaming app and aggregations
│   ├── ray/                 # Ray inference actors and models
│   │   ├── inference/       # Ray inference pipeline (consumer, actor)
│   │   ├── models/         # Model loaders and wrappers
│   │   └── training/       # Model training scripts
│   ├── api/                 # REST API (Flask)
│   ├── testers/             # Test consumers for each pipeline stage
│   └── utils/               # Configuration and utilities
├── frontend/                # React + TypeScript dashboard
├── models/                  # Trained ML models
├── docker-compose.yml       # Service orchestration (14 containers)
├── Dockerfile.*            # Container definitions
└── Documentation/          # Architecture and design docs
```

## Architecture

### System Design

The system follows a **Lambda Architecture** pattern with three distinct layers:

1. **Speed Layer (Real-time Processing)**
   - Kafka ingests raw weather data from NWS (National Weather Service) API
   - Spark Streaming processes data with sliding windows (5-minute windows, 1-minute slides)
   - Ray performs real-time ML inference on aggregated features using LSTM model

2. **Batch Layer (Model Training) [didn't implement here]**
   - Ray training cluster processes historical data
   - Models are trained and stored for inference

3. **Serving Layer**
   - API consumes predictions from Kafka
   - REST endpoints serve predictions to clients
   - Dashboard provides real-time visualization

### Data Pipeline

```
NWS (National Weather Service) API
    ↓ (HTTP requests every 15s, 5 stations)
Kafka Producer → weather-raw topic (4 partitions)
    ↓ (Spark Structured Streaming)
Spark Cluster → Aggregations & Feature Engineering
    ↓ (5-min sliding windows, 1-min slide)
weather-features topic (4 partitions)
    ↓ (Ray Inference Actors)
Ray Cluster → ML Inference (LSTM Forecasting - 7h horizon)
    ↓ (Parallel processing)
weather-predictions topic (4 partitions)
    ↓ (API Consumer)
REST API → HTTP Endpoints
    ↓
Frontend Dashboard → Real-time Visualization
```

**Status**: ✅ **Fully Operational** - All stages working end-to-end

### Component Responsibilities

- **Kafka**: Message queuing, decoupling components, fault-tolerant data storage
- **Spark**: Stateful stream processing, window aggregations, feature engineering
- **Ray**: Distributed ML inference, parallel prediction computation, model serving
- **API**: Prediction serving, real-time dashboard, system health monitoring

## Computing Resources Used

### Container Allocation

| Component | Containers | CPU per Container | RAM per Container | Total CPU | Total RAM |
|-----------|-----------|-------------------|-------------------|-----------|-----------|
| Kafka Broker | 1 | 1 | 2 GB | 1 | 2 GB |
| Kafka Data Collector | 1 | 0.5 | 1 GB | 0.5 | 1 GB |
| Spark Master | 1 | 1 | 2 GB | 1 | 2 GB |
| Spark Workers | 4 | 1 | 3 GB | 4 | 12 GB |
| Spark Streaming | 1 | 1 | 2 GB | 1 | 2 GB |
| Ray Head | 1 | 1 | 2 GB | 1 | 2 GB |
| Ray Workers | 4 | 1 | 3 GB | 4 | 12 GB |
| Ray Inference | 1 | 1 | 2 GB | 1 | 2 GB |
| API | 1 | 1 | 2 GB | 1 | 2 GB |
| **TOTAL** | **14** | - | - | **13.5** | **35 GB** |

### Resource Distribution

- **Total Containers**: 14 Docker containers
- **Total CPU Cores**: 13.5 cores allocated
- **Total Memory**: 35 GB RAM allocated
- **Network**: Single Docker bridge network (`weather-network`)
- **Storage**: Persistent volumes for Kafka data, Spark checkpoints, and model storage

### Scaling Characteristics

- **Horizontal Scaling**: Spark and Ray workers can be scaled independently
- **Partitioning**: Kafka topics use 4 partitions for parallel processing
- **Load Distribution**: Round-robin assignment for Ray actors and Spark tasks

**Components:**
- **Kafka**: Data ingestion and message queuing (3 topics: raw, features, predictions)
- **Spark**: Sliding window aggregations and feature engineering (1 master + 4 workers)
- **Ray**: ML inference for forecasting using LSTM model (1 head + 4 workers + inference consumer)
- **API**: REST API (Flask) for serving predictions
- **Frontend**: React + TypeScript dashboard for real-time visualization

## Technologies

- **Kafka**: Stream processing and message queuing
- **Apache Spark**: Distributed stream processing (Structured Streaming)
- **Ray**: Distributed ML inference framework
- **Python**: Core implementation language
- **Docker**: Containerization and orchestration

## Data Flow

1. **Producer** fetches weather data from NWS API every 15 seconds (5 stations)
2. **Spark Streaming** consumes raw data, applies 5-minute sliding windows, aggregates metrics
3. **Ray Inference** consumes aggregated features, performs forecasting (7-hour horizon) using LSTM model
4. **API** serves predictions via REST endpoints
5. **Frontend Dashboard** provides real-time visualization (React + TypeScript)

## Features

### ✅ Implemented Features

- ✅ **Real-time weather data ingestion** from 5 stations (Madison, Milwaukee, Chicago, Minneapolis, Des Moines) - **Kafka**
- ✅ **Sliding window aggregations** (mean, std, min, max) with 5-minute windows - **Spark**
- ✅ **Time series forecasting** (7-hour horizon) using LSTM model - **Ray**
- ✅ **Distributed processing** across multiple workers (4 Spark workers, 4 Ray workers) - **Kafka, Spark, Ray**
- ✅ **Fault-tolerant** with checkpointing - **Spark**
- ✅ **REST API endpoints** for predictions - **API** (Flask with CORS)
  - `/health` - Health check
  - `/predictions/latest` - Latest predictions
  - `/predictions` - Predictions with limit
  - `/topics/weather-raw` - Raw data by partition
  - `/topics/weather-features` - Features by partition
  - `/topics/weather-predictions` - Predictions by partition
  - `/stations/all` - All station data from all topics
- ✅ **Real-time dashboard** visualization - **Frontend** (React + TypeScript with Recharts, Leaflet)
- ✅ **Model training pipeline** - **Ray** (LSTM model trained and deployed)

### ⏳ Future Enhancements

- ⏳ **Anomaly detection** - Deferred to future phase (current XGBoost model not suitable for short-term anomalies)
- ⏳ **Extended forecasting horizon** - 24-hour predictions (requires model retraining)
- ⏳ **Time-aware features** - Add hour/day encoding to improve daily cycle prediction
- ⏳ **Historical sequence input** - Use actual historical data instead of repeated features

### Current Model

- **Forecasting Model**: `LSTM_FineTuned_20260124_193541`
  - Type: LSTM (Keras)
  - Features: temperature, wind_speed, dewpoint (metric units)
  - Lookback: 7 hours
  - Forecast horizon: 7 hours
  - Status: ✅ Trained and deployed

## Example Outputs (from testers)

The following testers can be used to verify data at each stage of the pipeline:

- **`debug_consumer.py`** - Consumes and displays raw weather data from the `weather-raw` Kafka topic. Verifies that the producer is correctly fetching and publishing weather data. Shows station_id, timestamp, temperature, humidity, wind_speed, pressure, and other raw observations.
  ```bash
  docker exec -it kafka python3 /app/src/testers/debug_consumer.py
  ```
  
  **Example Output:**
  ```
  Waiting for partition assignment...
  Consumer assigned to partitions: {TopicPartition(topic='weather-raw', partition=0), TopicPartition(topic='weather-raw', partition=1), TopicPartition(topic='weather-raw', partition=2), TopicPartition(topic='weather-raw', partition=3)}
  Starting to consume messages from topic 'weather-raw'...
  ================================================================================
  {'station_id': 'KMSN', 'station_name': 'Madison', 'timestamp': '2025-12-18T22:05:00+00:00', 'temperature': 33.8, 'humidity': 69.27, 'wind_speed': 20.376, 'wind_direction': 240, 'sea_level_pressure': 993.57, 'precipitation_last_hour': 0.0, 'partition': 1}
  {'station_id': 'KMKE', 'station_name': 'Milwaukee', 'timestamp': '2025-12-18T22:05:00+00:00', 'temperature': 39.2, 'humidity': 75.17, 'wind_speed': 20.376, 'wind_direction': 250, 'sea_level_pressure': 992.89, 'precipitation_last_hour': 0.0, 'partition': 2}
  {'station_id': 'KMDW', 'station_name': 'Chicago', 'timestamp': '2025-12-18T22:05:00+00:00', 'temperature': 39.2, 'humidity': 86.8, 'wind_speed': 18.504, 'wind_direction': 270, 'sea_level_pressure': 996.28, 'precipitation_last_hour': 0.0, 'partition': 3}
  {'station_id': 'KMSP', 'station_name': 'Minneapolis', 'timestamp': '2025-12-18T22:00:00+00:00', 'temperature': 15.8, 'humidity': 72.74, 'wind_speed': None, 'wind_direction': None, 'sea_level_pressure': 996.28, 'precipitation_last_hour': 0.0, 'partition': 1}
  {'station_id': 'KDSM', 'station_name': 'Des Moines', 'timestamp': '2025-12-18T22:00:00+00:00', 'temperature': 21.2, 'humidity': 62.54, 'wind_speed': 40.752, 'wind_direction': 300, 'sea_level_pressure': 1005.76, 'precipitation_last_hour': 0.0, 'partition': 3}
  ```

- **`test_spark_features.py`** - Consumes and displays aggregated weather features from the `weather-features` Kafka topic. Verifies that Spark streaming is correctly processing raw data, performing windowed aggregations (5-minute windows), and writing results. Shows temperature/humidity/pressure/wind statistics (mean, std, min, max) per window.
  ```bash
  docker exec -it spark-master python3 /app/src/testers/test_spark_features.py
  ```
  
  **Example Output:**
  ```
  Waiting for partition assignment...
  Consumer assigned to partitions: {TopicPartition(topic='weather-features', partition=0), TopicPartition(topic='weather-features', partition=1), TopicPartition(topic='weather-features', partition=2), TopicPartition(topic='weather-features', partition=3)}
  Starting to consume aggregated features from topic 'weather-features'...
  ================================================================================
  ✓ Using 'earliest' offset - will show all historical messages
    Reading from beginning of topic...
    Assigned to 4 partition(s)
  ================================================================================
  Waiting for messages... (Press Ctrl+C to stop)
  ================================================================================

  Checking for existing messages in topic...
  ✓ Found 75 message(s) in topic!
    Starting to display messages...


  ================================================================================
  Message #1 | Partition 1 | Station: KMSN
  ================================================================================
  Window: 2025-12-18 22:01:00 to 2025-12-18 22:06:00
  Measurements in window: 10

  Temperature:
    Mean: 33.8°F
    Std:  0.0
    Min:  33.8°F
    Max:  33.8°F

  Humidity:
    Mean: 69.27000000000001%
    Std:  0.0
    Min:  69.27%
    Max:  69.27%

  Pressure:
    Mean: 993.57 hPa
    Std:  6.397515720336034e-14
    Min:  993.57 hPa
    Max:  993.57 hPa

  Wind:
    Speed Mean: 20.375999999999998 m/s
    Direction:  240.0°

  Precipitation:
    Mean: 0.0 mm
    Max:  0.0 mm
  --------------------------------------------------------------------------------

  ================================================================================
  Message #2 | Partition 1 | Station: KMSP
  ================================================================================
  Window: 2025-12-18 21:58:00 to 2025-12-18 22:03:00
  Measurements in window: 10

  Temperature:
    Mean: 15.8°F
    Min:  72.74%
    Max:  72.74%

  Pressure:
    Mean: 996.28 hPa
    Std:  5.491595988356129e-14
    Min:  996.28 hPa
    Max:  996.28 hPa

  Wind:
    Speed Mean: 0.0 m/s
    Direction:  0.0°

  Precipitation:
    Mean: 0.0 mm
    Max:  0.0 mm
  --------------------------------------------------------------------------------
  ```

- **`test_ray_predictions.py`** - Consumes and displays predictions from the `weather-predictions` Kafka topic. Verifies that Ray inference is correctly generating forecasts using the LSTM model. Shows temperature predictions for the next 7 hours with confidence intervals.
  ```bash
  docker exec -it ray-head python3 /app/src/testers/test_ray_predictions.py
  ```

## Testing the Pipeline

### Verify End-to-End Flow

1. **Check Producer** (Raw Data):
   ```bash
   docker exec -it kafka python3 /app/src/testers/debug_consumer.py
   ```

2. **Check Spark** (Aggregated Features):
   ```bash
   docker exec -it spark-master python3 /app/src/testers/test_spark_features.py
   ```

3. **Check Ray** (Predictions):
   ```bash
   docker exec -it ray-head python3 /app/src/testers/test_ray_predictions.py
   ```

4. **Check API** (REST Endpoints):
   ```bash
   curl http://localhost:5000/health
   curl http://localhost:5000/predictions/latest
   curl http://localhost:5000/stations/all
   ```

### View Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f ray-inference
docker compose logs -f spark-streaming
docker compose logs -f api
```

## Frontend Dashboard

The project includes a React + TypeScript frontend dashboard located in the `frontend/` directory.

### Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Frontend Features

- Real-time weather station map (Leaflet)
- Time series charts for predictions (Recharts)
- Pipeline status monitoring
- System health metrics
- Kafka topic data visualization


## Moving on from this project
The same architecture could also be used for: 
- **IoT sensor monitoring**: Real-time processing of sensor data from smart devices, factories, or vehicles
- **Financial trading systems**: High-frequency trading data analysis, fraud detection, and risk assessment
- **E-commerce analytics**: Real-time recommendation systems, inventory management, and customer behavior analysis
- **Network security monitoring**: Anomaly detection in network traffic, intrusion detection, and threat analysis
- **Healthcare monitoring**: Patient vital signs tracking, predictive health analytics, and medical device data processing

- **Supply chain optimization**: Real-time tracking, demand forecasting, and logistics optimization

