# Comprehensive Benchmark Guide

This document outlines all benchmarks that should be included for this Lambda Architecture-based weather forecasting system integrating Kafka, Spark, and Ray.

## Overview

The project requires benchmarks across three main categories:
1. **Model Performance Benchmarks** - ML model accuracy and quality metrics
2. **System Performance Benchmarks** - Distributed system throughput, latency, and resource utilization
3. **Real-time Inference Benchmarks** - End-to-end pipeline performance under load

---

## 1. Model Performance Benchmarks

### 1.1 Forecasting Model Benchmarks ✅ (Currently Implemented)

**Location**: `models/benchmark_models.py`

**Purpose**: Evaluate trained forecasting models on test datasets.

**Metrics to Include**:

#### Accuracy Metrics
- **MAE (Mean Absolute Error)**: Average absolute difference between predictions and actuals
  - Unit: °F (or °C)
  - Lower is better
  - Target: < 3°F for temperature forecasting

- **RMSE (Root Mean Squared Error)**: Penalizes larger errors more
  - Unit: °F (or °C)
  - Lower is better
  - Target: < 4°F

- **MAPE (Mean Absolute Percentage Error)**: Percentage-based error metric
  - Unit: %
  - Lower is better
  - Target: < 10% for temperature

- **R² (Coefficient of Determination)**: Proportion of variance explained
  - Range: 0 to 1
  - Higher is better
  - Target: > 0.90

- **MSE (Mean Squared Error)**: Average squared differences
  - Unit: (°F)²
  - Lower is better

#### Time Series Specific Metrics
- **Directional Accuracy**: Percentage of correct trend predictions (up/down)
  - Unit: %
  - Higher is better
  - Target: > 65%

- **Mean Error (Bias)**: Average prediction bias
  - Unit: °F
  - Closer to 0 is better
  - Indicates systematic over/under-prediction

- **Std Error**: Standard deviation of errors
  - Unit: °F
  - Lower is better
  - Indicates prediction consistency

#### Visualizations
- Time series plots (true vs predicted)
- Scatter plots (true vs predicted)
- Residual analysis plots
- Error distribution histograms
- Model comparison charts

**Current Status**: ✅ Implemented in `models/benchmark_models.py`

---

### 1.2 Anomaly Detection Model Benchmarks ⏳ (To Be Implemented)

**Purpose**: Evaluate anomaly detection model performance.

**Metrics to Include**:

#### Classification Metrics
- **Precision**: True positives / (True positives + False positives)
  - Range: 0 to 1
  - Higher is better
  - Target: > 0.80

- **Recall (Sensitivity)**: True positives / (True positives + False negatives)
  - Range: 0 to 1
  - Higher is better
  - Target: > 0.75

- **F1-Score**: Harmonic mean of precision and recall
  - Range: 0 to 1
  - Higher is better
  - Target: > 0.77

- **Specificity**: True negatives / (True negatives + False positives)
  - Range: 0 to 1
  - Higher is better

- **False Positive Rate**: False positives / (False positives + True negatives)
  - Lower is better
  - Target: < 0.20

- **False Negative Rate**: False negatives / (False negatives + True positives)
  - Lower is better
  - Target: < 0.25

#### Additional Metrics
- **ROC-AUC**: Area under ROC curve
  - Range: 0 to 1
  - Higher is better
  - Target: > 0.85

- **PR-AUC**: Area under Precision-Recall curve
  - Range: 0 to 1
  - Higher is better
  - Useful for imbalanced datasets

- **Confusion Matrix**: Visual representation of classification results

**Implementation Location**: Should be added to `models/benchmark_models.py` or separate `benchmark_anomaly_models.py`

---

## 2. System Performance Benchmarks

### 2.1 End-to-End Latency ⏳ (To Be Implemented)

**Purpose**: Measure total time from data ingestion to prediction output.

**Metrics to Include**:

#### Component-Level Latency Breakdown
- **Kafka Ingestion Latency**: Time from API fetch to Kafka topic write
  - Target: < 100ms
  - Measurement: Timestamp at producer vs timestamp in Kafka

- **Spark Processing Latency**: Time from Kafka read to feature aggregation completion
  - Target: < 5 seconds (for 5-minute windows)
  - Measurement: Kafka consumer lag + processing time

- **Ray Inference Latency**: Time from feature consumption to prediction output
  - Target: < 1 second per prediction
  - Measurement: Time in inference actor

- **Total End-to-End Latency**: Sum of all component latencies
  - Target: < 1 minute (from raw data to prediction)
  - Measurement: End-to-end timestamp tracking

**Implementation**: Add latency tracking timestamps at each pipeline stage

---

### 2.2 Throughput Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure system capacity and message processing rates.

**Metrics to Include**:

- **Messages per Second (MPS)**: Total messages processed
  - Baseline: 1 message/second (single station)
  - Medium Load: 10 messages/second (10 stations)
  - High Load: 100 messages/second (100 stations)
  - Target: Handle 1000+ messages/second

- **Kafka Throughput**: Messages published/consumed per second
  - Producer throughput (weather-raw topic)
  - Consumer throughput (weather-features, weather-predictions topics)

- **Spark Processing Throughput**: Aggregated features produced per second
  - Dependent on window size and slide interval

- **Ray Inference Throughput**: Predictions generated per second
  - Dependent on model complexity and actor count

**Implementation**: Add throughput counters and timers in each component

---

### 2.3 Resource Utilization Benchmarks ⏳ (To Be Implemented)

**Purpose**: Monitor CPU, memory, and network usage across components.

**Metrics to Include**:

#### Per-Component Resource Usage
- **CPU Utilization**: Percentage of CPU cores used
  - Kafka: Monitor broker CPU
  - Spark: Monitor master and worker CPU
  - Ray: Monitor head and worker CPU
  - Target: < 80% average utilization

- **Memory Utilization**: RAM usage per container
  - Kafka: Monitor heap and off-heap memory
  - Spark: Monitor executor memory
  - Ray: Monitor actor memory
  - Target: < 85% of allocated memory

- **Network I/O**: Bytes sent/received per second
  - Kafka: Network traffic between broker and clients
  - Spark: Shuffle network traffic
  - Ray: Actor communication overhead

- **Disk I/O**: Read/write operations per second
  - Kafka: Log segment writes
  - Spark: Checkpoint writes
  - Ray: Model loading from disk

**Implementation**: Use Docker stats, Prometheus, or system monitoring tools

---

### 2.4 Scalability Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure performance with increasing load and resources.

**Test Scenarios**:

#### Horizontal Scaling Tests
1. **Baseline**: 1 Spark worker, 1 Ray worker
   - Measure: Latency, throughput, resource usage

2. **Medium Scale**: 2 Spark workers, 2 Ray workers
   - Measure: Improvement in throughput, latency reduction

3. **High Scale**: 4 Spark workers, 4 Ray workers (current setup)
   - Measure: Maximum sustainable throughput

4. **Stress Test**: Maximum workers (8+)
   - Measure: Bottleneck identification, saturation points

#### Load Scaling Tests
1. **Low Load**: 1 station, 1 message/second
2. **Medium Load**: 10 stations, 10 messages/second
3. **High Load**: 50 stations, 50 messages/second
4. **Extreme Load**: 100+ stations, 100+ messages/second

**Metrics to Track**:
- Throughput scaling factor (linear vs sub-linear)
- Latency degradation under load
- Resource utilization efficiency
- Bottleneck identification

---

### 2.5 Kafka-Specific Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure Kafka performance and health.

**Metrics to Include**:

- **Consumer Lag**: Delay between latest message and consumer position
  - Target: < 1000 messages lag
  - Critical threshold: > 10,000 messages

- **Topic Partition Distribution**: Message distribution across partitions
  - Ensure balanced load across 4 partitions

- **Producer/Consumer Throughput**: Messages per second per partition

- **Replication Lag**: Delay for replicated topics (if replication enabled)

**Implementation**: Use Kafka built-in metrics and monitoring tools

---

### 2.6 Spark-Specific Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure Spark streaming performance.

**Metrics to Include**:

- **Batch Processing Time**: Time to process each micro-batch
  - Target: < batch interval (e.g., < 1 minute for 1-minute batches)

- **Processing Delay**: Time from data arrival to output
  - Target: < 10 seconds

- **Checkpoint Write Time**: Time to write checkpoints
  - Affects fault tolerance recovery

- **State Store Size**: Size of windowed state
  - Monitor for memory growth

- **Task Execution Time**: Time per Spark task
  - Identify slow tasks

**Implementation**: Use Spark UI metrics and custom logging

---

### 2.7 Ray-Specific Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure Ray inference performance.

**Metrics to Include**:

- **Actor Startup Time**: Time to initialize inference actors
  - Target: < 5 seconds per actor

- **Model Loading Time**: Time to load model from disk
  - Target: < 10 seconds per model

- **Inference Latency per Prediction**: Time per single prediction
  - Target: < 100ms per prediction

- **Batch Inference Throughput**: Predictions per second per actor
  - Target: > 10 predictions/second per actor

- **Actor Memory Usage**: Memory per actor instance
  - Monitor for memory leaks

- **Actor Failure Rate**: Percentage of failed actor calls
  - Target: < 1%

**Implementation**: Use Ray dashboard metrics and custom timing

---

## 3. Real-Time Inference Benchmarks

### 3.1 Streaming Accuracy Benchmarks ⏳ (To Be Implemented)

**Purpose**: Measure model accuracy on live streaming data.

**Metrics to Include**:

- **Online MAE/RMSE**: Calculate accuracy metrics on streaming predictions
  - Compare against ground truth as it arrives
  - Update metrics in real-time

- **Prediction Drift**: Measure model performance degradation over time
  - Compare current accuracy vs baseline accuracy
  - Alert when drift exceeds threshold

- **Confidence Intervals**: Track prediction confidence scores
  - Identify low-confidence predictions
  - Monitor confidence distribution

**Implementation**: Add real-time accuracy tracking in API consumer

---

### 3.2 Anomaly Detection Performance ⏳ (To Be Implemented)

**Purpose**: Measure real-time anomaly detection effectiveness.

**Metrics to Include**:

- **Anomaly Detection Rate**: Anomalies detected per hour/day
  - Monitor for false positive spikes

- **Anomaly Severity Distribution**: Distribution of anomaly scores
  - Identify critical vs minor anomalies

- **Response Time**: Time from anomaly detection to alert
  - Target: < 5 seconds

**Implementation**: Add anomaly tracking and alerting system

---

## 4. Benchmark Implementation Plan

### Phase 1: Model Benchmarks ✅ (Completed)
- [x] Forecasting model accuracy benchmarks
- [x] Visualization generation
- [x] Model comparison tools

### Phase 2: System Performance Benchmarks ⏳ (To Do)
- [ ] End-to-end latency tracking
- [ ] Throughput measurement tools
- [ ] Resource utilization monitoring
- [ ] Scalability test suite

### Phase 3: Real-Time Benchmarks ⏳ (To Do)
- [ ] Streaming accuracy tracking
- [ ] Anomaly detection performance monitoring
- [ ] Real-time dashboard for benchmarks

### Phase 4: Integration & Reporting ⏳ (To Do)
- [ ] Automated benchmark runner
- [ ] Benchmark report generation
- [ ] Performance regression detection
- [ ] CI/CD integration

---

## 5. Recommended Benchmark Tools

### For Model Benchmarks
- **Current**: Custom Python scripts (`benchmark_models.py`)
- **Enhancement**: Add MLflow for experiment tracking

### For System Benchmarks
- **Docker Stats**: Container resource monitoring
- **Prometheus + Grafana**: System metrics collection and visualization
- **Kafka JMX Metrics**: Kafka performance monitoring
- **Spark UI**: Built-in Spark metrics
- **Ray Dashboard**: Built-in Ray metrics

### For End-to-End Testing
- **Locust**: Load testing framework
- **Apache Bench (ab)**: HTTP load testing
- **Custom Test Harness**: Pipeline-specific testing

---

## 6. Benchmark Execution

### Running Model Benchmarks
```bash
# Single model
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --model models/trained/forecasting/XGBoost_20260124_184642 \
    --output models/benchmark_results

# All models
python models/benchmark_models.py \
    --data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --output models/benchmark_results
```

### Running System Benchmarks (To Be Implemented)
```bash
# End-to-end latency test
python scripts/benchmark_system.py --test latency --duration 300

# Throughput test
python scripts/benchmark_system.py --test throughput --stations 10 --duration 600

# Scalability test
python scripts/benchmark_system.py --test scalability --workers 1,2,4,8
```

---

## 7. Benchmark Targets Summary

| Metric | Target | Current Status |
|--------|--------|----------------|
| **Forecasting MAE** | < 3°F | ✅ Measured |
| **Forecasting RMSE** | < 4°F | ✅ Measured |
| **Forecasting R²** | > 0.90 | ✅ Measured |
| **Anomaly Precision** | > 0.80 | ⏳ To Measure |
| **Anomaly Recall** | > 0.75 | ⏳ To Measure |
| **End-to-End Latency** | < 1 minute | ⏳ To Measure |
| **Ray Inference Latency** | < 100ms | ⏳ To Measure |
| **System Throughput** | 1000+ msg/sec | ⏳ To Measure |
| **CPU Utilization** | < 80% | ⏳ To Measure |
| **Memory Utilization** | < 85% | ⏳ To Measure |

---

## 8. Next Steps

1. **Implement System Performance Benchmarks**
   - Add latency tracking to pipeline components
   - Create throughput measurement tools
   - Set up resource monitoring

2. **Implement Anomaly Detection Benchmarks**
   - Add classification metrics to benchmark script
   - Create test dataset with labeled anomalies

3. **Create Automated Benchmark Suite**
   - Script to run all benchmarks
   - Generate comprehensive reports
   - Compare against baselines

4. **Set Up Continuous Benchmarking**
   - Integrate into CI/CD pipeline
   - Alert on performance regressions
   - Track performance over time

---

## References

- Current Model Benchmarking: `models/BENCHMARK_README.md`
- System Design: `Documentation/architecture.md`
- Performance Targets: `Documentation/improved_design.md`
