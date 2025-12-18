# Ultimate Stream and Distribute

UW Madison Fall 2025 Big Data System (CS544) final independent honors project. A Lambda Architecture-based real-time weather forecasting system integrating Kafka, Spark, and Ray for distributed stream processing and ML inference.

## Purpose

Ingests real-time weather data from multiple stations, processes it through Spark streaming for feature aggregation, and performs ML inference using Ray for forecasting and anomaly detection.

This project demonstrates a general-purpose multi-distributed system architecture for real-time stream processing and ML inference. While implemented for weather forecasting, the same architecture pattern can be applied to other domains such as:
- **Financial markets**: Stock price prediction, trading signal generation, fraud detection
- **IoT sensor networks**: Industrial monitoring, predictive maintenance, anomaly detection
- **E-commerce**: Real-time recommendation systems, demand forecasting, inventory optimization
- **Network security**: Intrusion detection, traffic analysis, threat prediction
- **Healthcare**: Patient monitoring, predictive analytics, medical device data processing

The core architecture (Kafka → Spark → Ray → API) remains the same; only the data sources, feature engineering, and ML models need to be adapted for each use case.


## Quick Start

```bash
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

## Project Structure

```
├── src/
│   ├── kafka_weather/      # Kafka producer and data collector
│   ├── spark/               # Spark streaming app and aggregations
│   ├── ray/                 # Ray inference actors and models
│   ├── api/                 # REST API and dashboard
│   └── utils/               # Configuration and utilities
├── docker-compose.yml       # Service orchestration
├── Dockerfile.*            # Container definitions
└── Documentation/          # Architecture and design docs
```

## Architecture

### System Design

The system follows a **Lambda Architecture** pattern with three distinct layers:

1. **Speed Layer (Real-time Processing)**
   - Kafka ingests raw weather data from Open-Meteo API
   - Spark Streaming processes data with sliding windows (5-minute windows, 1-minute slides)
   - Ray performs real-time ML inference on aggregated features

2. **Batch Layer (Model Training)**
   - Ray training cluster processes historical data
   - Models are trained and stored for inference

3. **Serving Layer**
   - API consumes predictions from Kafka
   - REST endpoints serve predictions to clients
   - Dashboard provides real-time visualization

### Data Pipeline

```
NOAA National Weather Service API
    ↓ (HTTP requests every 15s)
Kafka Producer → weather-raw topic (4 partitions)
    ↓ (Spark Structured Streaming)
Spark Cluster → Aggregations & Feature Engineering
    ↓ (5-min sliding windows)
weather-features topic (4 partitions)
    ↓ (Ray Inference Actors)
Ray Cluster → ML Inference (Forecasting + Anomaly Detection)
    ↓ (Parallel processing)
weather-predictions topic (4 partitions)
    ↓ (API Consumer)
REST API → HTTP Endpoints
```

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
- **Ray**: ML inference for forecasting and anomaly detection (1 head + 4 workers)
- **API**: REST API and dashboard for serving predictions

## Technologies

- **Kafka**: Stream processing and message queuing
- **Apache Spark**: Distributed stream processing (Structured Streaming)
- **Ray**: Distributed ML inference framework
- **Python**: Core implementation language
- **Docker**: Containerization and orchestration

## Data Flow

1. **Producer** fetches weather data from Open-Meteo API every 15 seconds
2. **Spark Streaming** consumes raw data, applies 5-minute sliding windows, aggregates metrics
3. **Ray Inference** consumes aggregated features, performs forecasting (24-hour horizon) and anomaly detection
4. **API** serves predictions via REST endpoints

## Features

- ✅ Real-time weather data ingestion from 5+ stations - **Kafka**
- ✅ Sliding window aggregations (mean, std, min, max) - **Spark**
- ✅ Time series forecasting (24-hour predictions) - **Ray**
- ⏳ Anomaly detection using statistical and ML models - **Ray** (basic implementation, ML models pending)
- ✅ Distributed processing across multiple workers - **Kafka, Spark, Ray**
- ✅ Fault-tolerant with checkpointing - **Spark**
- ⏳ REST API endpoints for predictions - **API** (structure in place, endpoints pending)
- ⏳ Real-time dashboard visualization - **API** (pending)
- ⏳ Model training pipeline - **Ray** (inference implemented, training pipeline pending)

## To Do

### High Priority

- [ ] **Complete REST API Implementation**
  - [ ] Implement Flask/FastAPI application with endpoints
  - [ ] Create `/predictions/{station_id}` endpoint
  - [ ] Create `/predictions/{station_id}/history` endpoint
  - [ ] Create `/anomalies` endpoint for recent anomalies
  - [ ] Create `/health` endpoint for system health checks
  - [ ] Create `/metrics` endpoint for performance metrics
  - [ ] Implement Kafka consumer for API to consume from `weather-predictions` topic

- [ ] **Enhance ML Models**
  - [ ] Upgrade anomaly detection from statistical to ML models (Isolation Forest/Autoencoder)
  - [ ] Improve forecasting model (upgrade from simple linear to LSTM/Prophet/XGBoost)
  - [ ] Implement model training pipeline with historical data
  - [ ] Add model versioning and management system
  - [ ] Implement model evaluation metrics (MAE, RMSE, MAPE for forecasting; Precision, Recall, F1 for anomaly)

- [ ] **Dashboard Implementation**
  - [ ] Create real-time dashboard frontend
  - [ ] Implement weather station map visualization
  - [ ] Add time series charts for predictions
  - [ ] Implement anomaly alerts/notifications
  - [ ] Add system health monitoring dashboard

### Medium Priority

- [ ] **Model Training Pipeline**
  - [ ] Set up Ray Train for distributed model training
  - [ ] Implement data loading from historical datasets
  - [ ] Create training scripts for forecasting and anomaly models
  - [ ] Implement model checkpointing during training
  - [ ] Add automated retraining pipeline

- [ ] **Testing & Validation**
  - [ ] Add comprehensive unit tests for all components
  - [ ] Implement integration tests for end-to-end pipeline
  - [ ] Add performance benchmarking tests
  - [ ] Validate model accuracy with test datasets

- [ ] **Documentation**
  - [ ] Complete API documentation
  - [ ] Add code comments and docstrings
  - [ ] Create deployment guide
  - [ ] Document model training procedures

### Low Priority / Future Enhancements

- [ ] **Performance Optimization**
  - [ ] Optimize Spark windowing performance
  - [ ] Optimize Ray inference latency
  - [ ] Implement caching mechanisms
  - [ ] Fine-tune resource allocation

- [ ] **Advanced Features**
  - [ ] Implement model A/B testing
  - [ ] Add model performance monitoring and alerts
  - [ ] Implement hot-reload for models without restart
  - [ ] Add support for more weather stations
  - [ ] Implement data persistence layer for historical queries

## Moving on from this project
The same architecture could also be used for: 
- **IoT sensor monitoring**: Real-time processing of sensor data from smart devices, factories, or vehicles
- **Financial trading systems**: High-frequency trading data analysis, fraud detection, and risk assessment
- **E-commerce analytics**: Real-time recommendation systems, inventory management, and customer behavior analysis
- **Network security monitoring**: Anomaly detection in network traffic, intrusion detection, and threat analysis
- **Healthcare monitoring**: Patient vital signs tracking, predictive health analytics, and medical device data processing
- **Supply chain optimization**: Real-time tracking, demand forecasting, and logistics optimization