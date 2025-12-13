# Implementation Design Document

## Overview
This project implements a Architecture similar to Lambda Architecture (https://www.geeksforgeeks.org/system-design/what-is-lambda-architecture-system-design/#what-is-lambda-architecture) for real-time weather forecasting. It builds upon course project p7: Kafka, Weather Data. It integrates three distinct distributed system to leverage their respective strengths:
- Kafka: High-throughput data ingestion and decoupling
- Spark: Stateful stream processing and data parallelism (ETL)
- Ray: Low-latency logical parallelism for Machine Learning inference

The System ingests raw weather station data, aggregates it using a sliding window in Spark to reduce noise, and passes the aggregated features to a Ray cluster to detect anomalies and predict future trends in real-time.

### Lambda Architecture Layers
The system implements a Lambda Architecture like structure with three distinct layers:

1. **Batch Layer**: Processes historical data for ML model training. Uses Ray distributed training on historical weather datasets to build forecasting and anomaly detection models.

2. **Speed Layer**: Handles real-time stream processing. Ingest raw data through Kafka, processes and aggregates in Spark, and performs real-time ML inference in Ray.

3. **Serving Layer**: Stores and serves prediction results. Results can be consumed via Kafka topics, REST APIs, or visualized in dashboards.

## Deployment
Deployment will be done on a single VM via Docker Compose. The cluster will consists of the following 5 primary type of containers:

1. kafka: Single broker, acting as the central nervous system
2. spark-master: coordinator for the ETL pipeline
3. spark-worker: executes the heavy windowing/aggregation tasks.
4. ray-head: manages the ML actors and serves the Ray Dashboard
5. ray-worker: executes the training/inference actors.

### Network Configuration
- All containers on a shared Docker network for inter-service communication
- Kafka exposed on port 9092 (internal) and 9093 (external if needed)
- Spark Master UI on port 8080
- Ray Dashboard on port 8265
- Zookeeper for Kafka coordination on port 2181

### Service Dependencies and Startup Order
1. Zookeeper (for Kafka coordination)
2. Kafka broker
3. Spark Master
4. Spark Workers
5. Ray Head
6. Ray Workers

Services should wait for dependencies to be healthy before starting.

## Communication Mechanisms

### Primary Approach: Kafka as Intermediary (Multi-Topic Architecture)

The system uses Kafka topics as the communication mechanism between components, providing decoupling, fault tolerance, and scalability.

#### Topic Architecture

1. **Topic 1: `weather-raw`** (Input Topic)
   - **Producer**: Weather API data producer or historical data replay script
   - **Consumer**: Spark Structured Streaming
   - **Purpose**: Buffer raw incoming weather station data
   - **Schema**: Raw weather measurements (temperature, humidity, pressure, wind speed, etc.)
   - **Partitioning**: By weather station ID for parallel processing

2. **Topic 2: `weather-features`** (Intermediate Topic)
   - **Producer**: Spark Structured Streaming (after aggregation/windowing)
   - **Consumer**: Ray inference workers
   - **Purpose**: Decouple Spark processing from Ray inference
   - **Schema**: Aggregated features (mean, std dev, min, max per window, station metadata)
   - **Partitioning**: By station ID to maintain order and enable parallel processing

3. **Topic 3: `weather-predictions`** (Output Topic - Optional)
   - **Producer**: Ray inference actors
   - **Consumer**: Dashboard/API services
   - **Purpose**: Store prediction results for visualization and querying
   - **Schema**: Predictions, anomaly flags, confidence scores, timestamps
   - **Partitioning**: By station ID or time-based

#### Benefits of Multi-Topic Architecture

- **Decoupling**: Each component operates independently; failures in one don't cascade
- **Scalability**: Scale Spark and Ray independently based on load
- **Fault Tolerance**: Data persists in Kafka; can replay from any point
- **Backpressure Handling**: Kafka buffers when downstream is slow
- **Multiple Consumers**: Multiple Ray workers can consume from same topic for load balancing
- **Replayability**: Reset consumer offsets to reprocess data

#### Consumer Groups

- **Spark Consumer Group**: `spark-weather-processors` - processes raw data
- **Ray Consumer Group**: `ray-ml-inference` - performs ML inference
- **Dashboard Consumer Group**: `dashboard-consumers` - displays results

### Alternative Communication Mechanisms

While Kafka is the primary approach, alternative mechanisms could be used:

1. **Ray Serve HTTP API**: Spark executors make HTTP requests to Ray Serve endpoints. Lower latency but tighter coupling.

2. **Direct Ray Client**: Spark executors use Ray client library for direct RPC calls. Lowest latency but requires Spark executors to be part of Ray cluster.

3. **Redis/RabbitMQ**: Lightweight message queue for high-throughput scenarios. Less persistence than Kafka.

## System Design

### Architecture Overview

The system follows a Lambda Architecture pattern with clear separation between batch processing (training) and real-time processing (inference).

```
┌─────────────────────────────────────────────────────────────┐
│                    BATCH LAYER (Training)                    │
│  Historical Data → Ray Training Cluster → Model Artifacts    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Model Loading)
┌─────────────────────────────────────────────────────────────┐
│                    SPEED LAYER (Inference)                   │
│  Real-time Data → Kafka → Spark → Kafka → Ray → Results     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVING LAYER                            │
│  Results Storage → Dashboard/API → Visualization            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Pipeline

#### Real-Time Inference Pipeline

1. **Data Ingestion**
   - Weather data source (Open-Meteo API or historical replay)
   - Producer writes to Kafka topic `weather-raw`
   - Messages include: station_id, timestamp, temperature, humidity, pressure, wind_speed, etc.

2. **Stream Processing (Spark)**
   - Spark Structured Streaming consumes from `weather-raw`
   - Applies sliding window (e.g., 5-minute windows, 1-minute slide)
   - Performs aggregations per station:
     - Mean, standard deviation, min, max for each metric
     - Feature engineering (e.g., temperature change rate, pressure trends)
   - Writes aggregated features to `weather-features` topic

3. **ML Inference (Ray)**
   - Ray workers consume from `weather-features` topic
   - Load pre-trained models from shared storage
   - Perform parallel inference:
     - Time series forecasting (predict next N hours)
     - Anomaly detection (identify unusual patterns)
   - Write results to `weather-predictions` topic (or directly to serving layer)

4. **Results Serving**
   - Dashboard/API consumes from `weather-predictions`
   - Real-time visualization of predictions and anomalies
   - Historical querying capabilities

#### Batch Training Pipeline

1. **Historical Data Collection**
   - Load historical weather data (Kaggle dataset or Kafka topic replay)
   - Preprocess and validate data

2. **Distributed Training (Ray)**
   - Use Ray Train or Ray actors for distributed training
   - Train models:
     - Time series forecasting model (LSTM, Prophet, or ARIMA)
     - Anomaly detection model (Isolation Forest, Autoencoder)
   - Hyperparameter tuning with Ray Tune (optional)

3. **Model Management**
   - Save model artifacts to shared storage (local filesystem, S3, or MinIO)
   - Version models with timestamps
   - Evaluate model performance on validation set

4. **Model Deployment**
   - Load latest model in Ray inference actors
   - A/B testing capability for model updates
   - Rollback mechanism if new model performs worse

### Component Details

#### Kafka Layer

**Topics Configuration:**
- `weather-raw`: 
  - Partitions: Number of weather stations (for parallel processing)
  - Replication: 1 (single broker setup)
  - Retention: 7 days
  - Compression: Snappy

- `weather-features`:
  - Partitions: Number of stations (maintains order per station)
  - Replication: 1
  - Retention: 24 hours
  - Compression: Snappy

- `weather-predictions`:
  - Partitions: Number of stations or time-based
  - Replication: 1
  - Retention: 30 days (for historical analysis)
  - Compression: Snappy

**Consumer Groups:**
- Offset management: Automatic commit with manual checkpointing in Spark
- Consumer lag monitoring for performance tracking

#### Spark Layer

**Structured Streaming Configuration:**
- Processing mode: Continuous or micro-batch (default: micro-batch)
- Checkpoint location: HDFS or local filesystem for fault tolerance
- Watermark: Handle late-arriving data (e.g., 10 minutes)
- Trigger: Processing time trigger (e.g., every 1 minute)

**Window Operations:**
- Window type: Sliding window
- Window duration: 5 minutes
- Slide duration: 1 minute
- Aggregations per window:
  - Mean, std dev, min, max for temperature, humidity, pressure, wind speed
  - Count of measurements
  - Feature engineering: rate of change, trends

**State Management:**
- State store: RocksDB for efficient state storage
- Checkpointing: Every batch for recovery
- State cleanup: TTL-based cleanup for old state

**Output Format:**
- JSON or Avro format for feature vectors
- Schema: station_id, window_start, window_end, aggregated_features, metadata

#### Ray Layer

**Actor Architecture:**
- **Inference Actors**: Stateless actors that load models and perform inference
  - Model loading: On actor initialization or periodic refresh
  - Batch inference: Process multiple feature vectors in parallel
  - Result formatting: Standardized prediction output

- **Training Actors** (for batch training):
  - Distributed data loading
  - Model training with parameter server or all-reduce
  - Model checkpointing during training

**Model Serving:**
- Option 1: Ray Serve for HTTP-based serving (if using HTTP communication)
- Option 2: Direct actor calls from Kafka consumers
- Model versioning: Load models by version tag
- Model updates: Hot-swap models without stopping inference

**Parallelism:**
- One inference actor per Ray worker (or configurable)
- Parallel processing of Kafka partitions
- Object store for large intermediate data

### Lambda Architecture Layers

#### Batch Layer
- **Purpose**: Process historical data for model training
- **Technology**: Ray distributed training
- **Frequency**: Daily or weekly retraining
- **Input**: Historical weather data (Kaggle dataset or Kafka topic replay)
- **Output**: Trained model artifacts stored in shared storage

#### Speed Layer
- **Purpose**: Real-time stream processing and inference
- **Technology**: Kafka + Spark + Ray
- **Latency Target**: End-to-end < 1 minute (from raw data to prediction)
- **Input**: Real-time weather data stream
- **Output**: Real-time predictions and anomaly flags

#### Serving Layer
- **Purpose**: Store and serve prediction results
- **Technology**: Kafka topics + optional database (PostgreSQL, InfluxDB) + REST API
- **Query Interface**: REST API endpoints for historical queries
- **Visualization**: Real-time dashboard (Grafana, custom web app)

### ML Model Integration

#### Model Types

1. **Time Series Forecasting Model**
   - Predict temperature, humidity, pressure for next N hours (e.g., 6-24 hours)
   - Model options: LSTM, Prophet, ARIMA, or XGBoost with time features
   - Input: Aggregated features from Spark (sliding window statistics)
   - Output: Forecasted values with confidence intervals

2. **Anomaly Detection Model**
   - Identify unusual weather patterns
   - Model options: Isolation Forest, Autoencoder, or statistical methods
   - Input: Current features vs. historical patterns
   - Output: Anomaly score and binary flag

#### Training vs Inference Separation

- **Training**: Offline batch job using Ray distributed training
  - Runs separately from real-time pipeline
  - Uses historical data
  - Produces model artifacts
  - Scheduled periodically (daily/weekly)

- **Inference**: Real-time processing in Ray actors
  - Loads pre-trained models
  - Processes streaming features from Kafka
  - Low-latency predictions
  - Runs continuously

#### Model Management

- **Storage**: Shared filesystem or object storage (S3, MinIO)
- **Versioning**: Timestamp-based or semantic versioning
- **Loading**: Models loaded on Ray actor initialization
- **Updates**: Hot-reload capability or graceful restart
- **A/B Testing**: Run multiple model versions in parallel

### State Management

#### Spark State
- **Checkpointing**: Regular checkpoints to durable storage
- **State Store**: RocksDB for windowed aggregations
- **Recovery**: Automatic recovery from checkpoints on failure
- **State Cleanup**: TTL-based cleanup for expired windows

#### Ray Model State
- **Model Loading**: Load models from shared storage on startup
- **Model Caching**: Keep models in memory for fast inference
- **Model Updates**: Periodic refresh or event-driven updates
- **State Persistence**: Model artifacts in shared storage

### Error Handling & Fault Tolerance

#### Kafka
- **Offset Management**: Automatic offset commits with manual checkpointing
- **Consumer Lag**: Monitor and alert on high lag
- **Retry Logic**: Automatic retries for transient failures
- **Dead Letter Queue**: Handle messages that fail processing repeatedly

#### Spark
- **Checkpoint Recovery**: Recover from last checkpoint on failure
- **Watermarking**: Handle late-arriving data gracefully
- **Backpressure**: Automatic backpressure handling
- **Failure Handling**: Restart failed tasks automatically

#### Ray
- **Actor Failure**: Restart failed actors automatically
- **Model Loading Errors**: Fallback to previous model version
- **Inference Errors**: Log errors and continue processing
- **Resource Management**: Handle OOM and resource exhaustion

### Data Schema

#### Input Schema (weather-raw topic)
```json
{
  "station_id": "string",
  "timestamp": "datetime",
  "temperature": "float",
  "humidity": "float",
  "pressure": "float",
  "wind_speed": "float",
  "wind_direction": "float",
  "precipitation": "float"
}
```

#### Intermediate Schema (weather-features topic)
```json
{
  "station_id": "string",
  "window_start": "datetime",
  "window_end": "datetime",
  "features": {
    "temp_mean": "float",
    "temp_std": "float",
    "temp_min": "float",
    "temp_max": "float",
    "humidity_mean": "float",
    "pressure_mean": "float",
    "wind_speed_mean": "float",
    "measurement_count": "int"
  },
  "metadata": {
    "processing_timestamp": "datetime"
  }
}
```

#### Output Schema (weather-predictions topic)
```json
{
  "station_id": "string",
  "timestamp": "datetime",
  "predictions": {
    "temperature_6h": "float",
    "temperature_12h": "float",
    "humidity_6h": "float",
    "pressure_6h": "float"
  },
  "anomaly": {
    "is_anomaly": "boolean",
    "anomaly_score": "float",
    "anomaly_type": "string"
  },
  "confidence": {
    "temperature_confidence": "float",
    "overall_confidence": "float"
  },
  "model_version": "string"
}
```

## ML Training Architecture

### Training Component Overview

ML training is performed as a separate batch job using Ray distributed training. This is distinct from the real-time inference pipeline and runs periodically on historical data.

### Training Pipeline

#### 1. Data Preparation
- **Source**: Historical weather data from Kaggle dataset or Kafka topic replay
- **Preprocessing**:
  - Data cleaning (handle missing values, outliers)
  - Feature engineering (time-based features, lag features)
  - Train/validation/test split
  - Data normalization/scaling

#### 2. Distributed Training with Ray
- **Framework**: Ray Train or custom Ray actors
- **Model Types**:
  - **Forecasting Model**: LSTM, Prophet, or time series regression
  - **Anomaly Detection Model**: Isolation Forest, Autoencoder, or statistical methods
- **Training Strategy**:
  - Data parallelism: Distribute data across Ray workers
  - Model parallelism: For large models (if needed)
  - Hyperparameter tuning: Ray Tune for automated hyperparameter search

#### 3. Model Evaluation
- **Metrics**:
  - Forecasting: MAE, RMSE, MAPE for predictions
  - Anomaly Detection: Precision, Recall, F1-score
- **Validation**: Cross-validation or time-based validation
- **Model Selection**: Best model based on validation metrics

#### 4. Model Management
- **Storage**: Save model artifacts to shared storage
  - Model weights/parameters
  - Preprocessing scalers/encoders
  - Model metadata (version, training date, metrics)
- **Versioning**: Timestamp-based or semantic versioning (v1.0, v1.1, etc.)
- **Registry**: Track model versions and performance metrics

#### 5. Model Deployment
- **Loading**: Ray inference actors load models from shared storage
- **Hot Reload**: Update models without stopping inference (graceful restart)
- **A/B Testing**: Run multiple model versions in parallel for comparison
- **Rollback**: Revert to previous model version if new model underperforms

### Training vs Inference Separation

**Training (Batch/Offline)**:
- Runs separately from real-time pipeline
- Uses historical data (weeks/months of data)
- Computationally intensive, can take hours
- Scheduled periodically (daily/weekly)
- Produces model artifacts

**Inference (Real-time)**:
- Part of real-time streaming pipeline
- Uses current aggregated features
- Low-latency requirement (< 1 second per prediction)
- Runs continuously
- Loads pre-trained models

### Model Update Strategy

1. **Periodic Retraining**: Retrain models daily/weekly on new historical data
2. **Triggered Retraining**: Retrain when model performance degrades
3. **Incremental Updates**: For models that support online learning (future enhancement)
4. **Version Control**: Maintain multiple model versions for A/B testing
5. **Performance Monitoring**: Track prediction accuracy and model drift

## Client Interface

### Dashboard/Visualization
- **Real-time Monitoring**: Live updates of predictions and anomalies
- **Weather Station Map**: Geographic visualization of stations
- **Time Series Charts**: Historical and predicted values
- **Anomaly Alerts**: Highlight unusual patterns
- **Metrics Dashboard**: System health, latency, throughput

### API Endpoints
- **GET /predictions/{station_id}**: Get latest predictions for a station
- **GET /predictions/{station_id}/history**: Get historical predictions
- **GET /anomalies**: Get recent anomalies across all stations
- **GET /health**: System health check
- **GET /metrics**: Performance metrics

### Real-time Monitoring
- **Kafka Consumer Lag**: Monitor processing delays
- **Spark Streaming Metrics**: Batch processing times, throughput
- **Ray Actor Status**: Actor health, inference latency
- **Model Performance**: Prediction accuracy, anomaly detection rate
- **System Resources**: CPU, memory, network usage

## Evaluation & Performance

### Metrics to Measure

#### System Performance
- **End-to-end Latency**: Time from raw data ingestion to prediction output
  - Target: < 1 minute
  - Breakdown: Kafka ingestion, Spark processing, Ray inference
- **Throughput**: Messages processed per second
  - Target: Handle 1000+ messages/second
- **Resource Utilization**: CPU, memory, network usage per component
- **Scalability**: Performance with increasing load (stations, data rate)

#### ML Model Performance
- **Forecasting Accuracy**:
  - MAE (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - MAPE (Mean Absolute Percentage Error)
- **Anomaly Detection Performance**:
  - Precision, Recall, F1-score
  - False positive/negative rates
- **Model Inference Latency**: Time per prediction
  - Target: < 100ms per prediction

### Scalability Considerations

- **Horizontal Scaling**: Add more Spark workers and Ray workers as load increases
- **Kafka Partitioning**: Increase partitions for parallel processing
- **Resource Allocation**: Tune memory and CPU per container
- **Bottleneck Identification**: Profile each component to find bottlenecks

### Performance Benchmarks

- **Baseline**: Single station, 1 message/second
- **Medium Load**: 10 stations, 10 messages/second
- **High Load**: 100 stations, 100 messages/second
- **Stress Test**: Maximum sustainable throughput

### Resource Allocation per Component

- **Kafka**: 2GB RAM, 2 CPU cores
- **Spark Master**: 2GB RAM, 1 CPU core
- **Spark Worker**: 4GB RAM, 2 CPU cores (per worker)
- **Ray Head**: 4GB RAM, 2 CPU cores
- **Ray Worker**: 4GB RAM, 2 CPU cores (per worker)

Adjust based on actual workload and available resources.

## Project Roadmap / Todo

### Phase 1: Infrastructure Setup (Week 1)
- [ ] Set up Docker Compose with all services
- [ ] Configure Kafka topics and consumer groups
- [ ] Set up Spark Structured Streaming basic pipeline
- [ ] Set up Ray cluster with basic actors
- [ ] Test basic data flow: Kafka → Spark → Kafka

### Phase 2: Data Processing (Week 2)
- [ ] Implement Spark windowing and aggregation logic
- [ ] Define and implement data schemas
- [ ] Set up data producer (API or replay script)
- [ ] Test end-to-end: Data → Kafka → Spark → Kafka

### Phase 3: ML Integration (Week 3)
- [ ] Implement Ray training pipeline for historical data
- [ ] Train initial forecasting and anomaly detection models
- [ ] Implement Ray inference actors
- [ ] Integrate inference into real-time pipeline
- [ ] Test: Kafka → Spark → Kafka → Ray → Results

### Phase 4: Model Management (Week 4)
- [ ] Implement model storage and versioning
- [ ] Set up model loading in Ray actors
- [ ] Implement model update mechanism
- [ ] Add model performance monitoring

### Phase 5: Client Interface (Week 5)
- [ ] Build dashboard/visualization
- [ ] Implement REST API endpoints
- [ ] Add real-time monitoring
- [ ] Create documentation

### Phase 6: Evaluation & Optimization (Week 6)
- [ ] Performance benchmarking
- [ ] Scalability testing
- [ ] Optimize bottlenecks
- [ ] Final documentation and report

### Milestones
1. **M1**: Basic pipeline working (Kafka → Spark → Kafka)
2. **M2**: ML inference integrated (end-to-end with predictions)
3. **M3**: Training pipeline complete
4. **M4**: Full system with dashboard
5. **M5**: Performance optimized and documented

### Deliverables
- Working Docker Compose setup
- Source code for all components
- Trained ML models
- Dashboard/API interface
- Detailed documentation report (due December 16)

## Data or Dataset
- Method 1: Live API: Open-Meteo free weather api: https://open-meteo.com/
- Method 2: Historical Replay: Historical Hourly Weather Data 2012-2017 from Kaggle: https://www.kaggle.com/datasets/selfishgene/historical-hourly-weather-data

