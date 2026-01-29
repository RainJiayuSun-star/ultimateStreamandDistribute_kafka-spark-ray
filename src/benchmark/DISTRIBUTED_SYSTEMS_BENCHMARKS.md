# Distributed Systems Benchmarks Guide

**Focus**: Kafka, Spark, and Ray performance, scalability, and reliability metrics for the Lambda Architecture weather forecasting pipeline.

---

## Overview

This guide outlines comprehensive benchmarks for evaluating the distributed systems components:
- **Kafka**: Message queuing, throughput, consumer lag
- **Spark**: Stream processing, windowing, checkpointing
- **Ray**: Distributed inference, actor performance, parallel processing
- **End-to-End Pipeline**: Total latency, throughput, fault tolerance

---

## 1. End-to-End Pipeline Benchmarks

### 1.1 Pipeline Latency

**Purpose**: Measure total time from data ingestion to prediction output.

**Pipeline Stages**:
```
Open-Meteo API → Kafka Producer → weather-raw topic 
→ Spark Streaming → weather-features topic 
→ Ray Inference → weather-predictions topic 
→ API Consumer
```

**Metrics to Measure**:

#### Stage-Level Latency
- **T1: Producer Latency**: API fetch → Kafka write
  - Target: < 100ms
  - Measurement: Timestamp at API call vs Kafka message timestamp

- **T2: Kafka → Spark Latency**: Message in Kafka → Spark processing start
  - Target: < 500ms
  - Measurement: Kafka message timestamp vs Spark batch start time

- **T3: Spark Processing Latency**: Spark read → Feature aggregation → Kafka write
  - Target: < 5 seconds (for 5-minute windows)
  - Measurement: Spark batch processing time + write time

- **T4: Kafka → Ray Latency**: Feature message → Ray actor call
  - Target: < 200ms
  - Measurement: Kafka message timestamp vs Ray actor invocation

- **T5: Ray Inference Latency**: Actor call → Prediction output
  - Target: < 1 second per prediction
  - Measurement: Time in inference actor

- **T6: Kafka → API Latency**: Prediction message → API availability
  - Target: < 100ms
  - Measurement: Kafka message timestamp vs API query time

**Total End-to-End Latency**: T1 + T2 + T3 + T4 + T5 + T6
- **Target**: < 1 minute (from raw data to prediction available via API)
- **Critical Threshold**: > 2 minutes indicates system bottleneck

**Implementation**:
- Add timestamps at each stage: `ingestion_time`, `kafka_time`, `spark_time`, `ray_time`, `api_time`
- Track in message metadata or separate monitoring system

---

### 1.2 Pipeline Throughput

**Purpose**: Measure messages processed per second across the entire pipeline.

**Metrics**:

- **Producer Throughput**: Messages published to `weather-raw` per second
  - Baseline: 1 msg/sec (single station)
  - Medium: 10 msg/sec (10 stations)
  - High: 100 msg/sec (100 stations)
  - Target: 1000+ msg/sec sustained

- **Spark Throughput**: Aggregated features produced per second
  - Dependent on window size (5-minute windows)
  - Should match producer throughput (accounting for windowing)

- **Ray Throughput**: Predictions generated per second
  - Dependent on actor count and inference latency
  - Target: Match Spark throughput

- **End-to-End Throughput**: Complete pipeline messages/second
  - Measure at final output (weather-predictions topic)
  - Should match producer throughput (no message loss)

**Implementation**:
- Count messages per second at each Kafka topic
- Use Kafka consumer groups to track consumption rates
- Monitor Spark batch completion rates

---

## 2. Kafka Benchmarks

### 2.1 Producer Performance

**Metrics**:

- **Producer Throughput**: Messages/second published
  - Measure per partition (4 partitions)
  - Target: 250+ msg/sec per partition (1000+ total)

- **Producer Latency**: Time from API fetch to Kafka acknowledgment
  - Target: < 100ms p95
  - Measure: `producer.send()` call to callback

- **Producer Error Rate**: Failed publishes / total publishes
  - Target: < 0.1%
  - Monitor: Retries, timeouts, connection errors

- **Message Size**: Average bytes per message
  - Monitor: Network bandwidth usage
  - Target: < 10KB per message (JSON)

**Tools**: Kafka producer metrics (JMX), custom logging

---

### 2.2 Consumer Performance

**Metrics**:

- **Consumer Lag**: Messages behind latest offset
  - **Spark Consumer Lag**: `weather-raw` topic
    - Target: < 1000 messages
    - Critical: > 10,000 messages
  - **Ray Consumer Lag**: `weather-features` topic
    - Target: < 500 messages
    - Critical: > 5,000 messages
  - **API Consumer Lag**: `weather-predictions` topic
    - Target: < 100 messages
    - Critical: > 1,000 messages

- **Consumer Throughput**: Messages consumed per second
  - Per consumer group
  - Per partition
  - Target: Match producer throughput

- **Consumer Processing Time**: Time to process each message batch
  - Spark: Batch processing time
  - Ray: Actor inference time
  - Target: < batch interval

**Tools**: 
- `kafka-consumer-groups.sh` for lag monitoring
- Kafka JMX metrics: `records-lag`, `records-consumed-rate`

---

### 2.3 Topic and Partition Performance

**Metrics**:

- **Partition Distribution**: Messages per partition
  - Ensure balanced load across 4 partitions
  - Monitor: Partition leader distribution
  - Target: ±10% variance across partitions

- **Topic Size**: Total messages in topic
  - Monitor: `weather-raw`, `weather-features`, `weather-predictions`
  - Alert: Rapid growth indicates consumer lag

- **Replication**: Replication factor and lag (if replication enabled)
  - Monitor: ISR (In-Sync Replicas) count
  - Target: All replicas in sync

**Tools**: Kafka admin tools, JMX metrics

---

## 3. Spark Streaming Benchmarks

### 3.1 Batch Processing Performance

**Metrics**:

- **Batch Processing Time**: Time to process each micro-batch
  - Target: < batch interval (e.g., < 1 minute for 1-minute batches)
  - Critical: If processing time > batch interval, batches will queue up
  - Measurement: Spark UI → Streaming tab → Batch Duration

- **Scheduling Delay**: Time between batch trigger and actual start
  - Target: < 1 second
  - Indicates resource contention

- **Processing Delay**: Time from data arrival to output
  - Target: < 10 seconds
  - Includes: Kafka read + processing + Kafka write

- **Total Delay**: End-to-end delay through Spark
  - Target: < 15 seconds
  - Measurement: Input timestamp → Output timestamp

**Tools**: Spark UI (http://localhost:8080), Spark metrics API

---

### 3.2 Windowing and Aggregation Performance

**Metrics**:

- **Window Processing Time**: Time to aggregate 5-minute windows
  - Target: < 2 seconds per window
  - Monitor: Per-station window processing

- **State Store Size**: Size of windowed state in memory
  - Monitor: Growth over time
  - Alert: Rapid growth indicates memory leak
  - Target: Stable size (depends on window retention)

- **State Store Operations**: Read/write operations per second
  - Monitor: State store I/O
  - Target: < 1000 ops/sec

- **Watermark Processing**: Watermark delay
  - Monitor: Late data handling
  - Target: < 1 minute watermark delay

**Tools**: Spark UI → Streaming → State Store, Spark metrics

---

### 3.3 Checkpointing and Fault Tolerance

**Metrics**:

- **Checkpoint Write Time**: Time to write checkpoint
  - Target: < 5 seconds
  - Affects: Recovery time after failure

- **Checkpoint Size**: Size of checkpoint files
  - Monitor: Disk usage
  - Target: < 1GB per checkpoint

- **Recovery Time**: Time to recover from checkpoint after restart
  - Target: < 30 seconds
  - Measurement: Spark restart → first batch processed

- **Checkpoint Frequency**: How often checkpoints are written
  - Current: Every batch interval
  - Monitor: Disk I/O impact

**Tools**: Spark checkpoint directory monitoring, Spark UI

---

### 3.4 Resource Utilization

**Metrics**:

- **Executor CPU Usage**: CPU utilization per Spark executor
  - Target: 60-80% average
  - Alert: > 90% indicates CPU bottleneck

- **Executor Memory Usage**: Memory usage per executor
  - Target: < 85% of allocated memory (3GB per worker)
  - Alert: > 90% indicates memory pressure

- **Shuffle Read/Write**: Network I/O for data shuffling
  - Monitor: Shuffle bytes read/written
  - Target: Minimize shuffle (local processing preferred)

- **Task Execution Time**: Time per Spark task
  - Monitor: Slow tasks (outliers)
  - Target: < 1 second per task average

**Tools**: Spark UI → Executors tab, Docker stats

---

## 4. Ray Benchmarks

### 4.1 Actor Performance

**Metrics**:

- **Actor Startup Time**: Time to initialize inference actors
  - Target: < 5 seconds per actor
  - Measurement: Actor creation → ready state
  - Monitor: Initialization overhead

- **Actor Count**: Number of active inference actors
  - Current: 4 actors (one per Ray worker)
  - Monitor: Actor distribution across workers
  - Target: Balanced distribution

- **Actor Memory Usage**: Memory per actor instance
  - Target: < 500MB per actor (model + state)
  - Monitor: Memory leaks over time
  - Alert: Growing memory indicates leak

- **Actor Failure Rate**: Percentage of failed actor calls
  - Target: < 1%
  - Monitor: Exceptions, timeouts, OOM errors

**Tools**: Ray Dashboard (http://localhost:8265), Ray metrics API

---

### 4.2 Inference Performance

**Metrics**:

- **Inference Latency**: Time per single prediction
  - Target: < 100ms p95
  - Measurement: Actor call → prediction returned
  - Monitor: P50, P95, P99 percentiles

- **Batch Inference Throughput**: Predictions per second per actor
  - Target: > 10 predictions/second per actor
  - With 4 actors: > 40 predictions/second total

- **Model Loading Time**: Time to load model from disk
  - Target: < 10 seconds per model
  - Measurement: Model file read → model ready
  - Occurs: Actor initialization or model reload

- **Inference Queue Depth**: Pending inference requests
  - Target: < 10 pending requests
  - Alert: > 100 indicates actor bottleneck

**Tools**: Ray Dashboard → Actors, custom timing in `ray_consumer.py`

---

### 4.3 Ray Cluster Performance

**Metrics**:

- **Cluster CPU Usage**: CPU utilization across Ray workers
  - Target: 60-80% average
  - Monitor: Per-worker CPU usage
  - Alert: > 90% indicates CPU bottleneck

- **Cluster Memory Usage**: Memory usage across Ray workers
  - Target: < 85% of allocated memory (3GB per worker)
  - Monitor: Object store memory usage
  - Alert: > 90% indicates memory pressure

- **Object Store Performance**: Object store read/write throughput
  - Monitor: Object store I/O
  - Target: < 100MB/s per worker

- **Actor Communication Overhead**: Time for actor-to-actor calls
  - Target: < 10ms per call
  - Monitor: Network latency between workers

**Tools**: Ray Dashboard → Cluster, Ray metrics API

---

## 5. Scalability Benchmarks

### Scaling Priority Summary

**For this Lambda Architecture project, scaling priorities are:**

1. **Spark Worker Scaling** (HIGHEST PRIORITY)
   - Primary bottleneck: Stream processing and windowing
   - Impact: Direct linear throughput improvement
   - Current: 4 workers → Test scaling to 1, 2, 4, 8 workers

2. **Ray Worker Scaling** (HIGH PRIORITY)
   - Primary bottleneck: ML inference processing
   - Impact: Direct linear throughput improvement
   - Current: 4 workers → Test scaling to 1, 2, 4, 8 workers

3. **Kafka Partition Scaling** (MEDIUM PRIORITY)
   - Impact: Parallelism for Spark consumers
   - Current: 4 partitions (matches 4 Spark workers - optimal)
   - Test: 2, 4, 8 partitions to understand impact

4. **Kafka Broker Scaling** (LOW PRIORITY)
   - Impact: Fault tolerance and storage capacity (not throughput)
   - Current: 1 broker (sufficient for this workload)
   - Only needed: If implementing replication or very high throughput (>100K msg/sec)

**Key Insight**: 
- **Compute scaling (Spark/Ray workers)** provides immediate throughput gains
- **Kafka partition count** should match Spark worker count for optimal parallelism
- **Kafka broker count** is for fault tolerance, not throughput (single broker handles 10K-100K+ msg/sec)

---

### 5.1 Horizontal Scaling Tests

**Purpose**: Measure performance improvement with additional workers.

**Scaling Priority**: 
- **Primary Focus**: Spark and Ray workers (compute bottlenecks)
- **Secondary**: Kafka partition count (parallelism)
- **Tertiary**: Kafka broker count (fault tolerance and capacity)

**Why Spark/Ray Workers Are More Important**:
- **Compute-bound operations**: Spark windowing/aggregation and Ray inference are CPU-intensive
- **Direct throughput impact**: More workers = more parallel processing = higher throughput
- **Linear scaling**: Adding workers typically provides near-linear throughput improvement
- **Current bottleneck**: In this Lambda Architecture, processing (Spark/Ray) is typically the bottleneck, not message queuing

**Kafka Scaling Considerations**:
- **Partition count matters more than broker count**: Partitions determine parallelism; a single broker can handle high throughput with proper partitioning
- **Broker scaling is for**: Fault tolerance (replication), storage capacity, and very high throughput scenarios (>100K msg/sec)
- **Current setup**: Single Kafka broker with 4 partitions is sufficient for most workloads
- **When to scale Kafka brokers**: When you need replication (fault tolerance) or when single broker becomes a bottleneck (rare)

---

#### Spark Worker Scaling (PRIMARY FOCUS)

**Purpose**: Measure throughput improvement with additional Spark workers.

**Test Scenarios**:

1. **Baseline**: 1 Spark worker
   - Measure: Throughput, latency, resource usage
   - Expected: ~250 msg/sec
   - **Bottleneck**: Single worker processing all partitions

2. **2 Workers**: 2 Spark workers
   - Measure: Throughput improvement
   - Expected: ~500 msg/sec (2x improvement)
   - **Bottleneck**: Worker parallelism

3. **4 Workers**: 4 Spark workers (current)
   - Measure: Maximum throughput
   - Expected: ~1000 msg/sec (4x improvement)
   - **Bottleneck**: Matches 4 Kafka partitions (optimal)

4. **8 Workers**: Stress test
   - Measure: Saturation point, bottleneck identification
   - Expected: Diminishing returns (Kafka partition limit or CPU bottleneck)
   - **Note**: More workers than partitions may not help much

**Metrics to Track**:
- Throughput scaling factor (linear vs sub-linear)
- Latency reduction per worker added
- Resource utilization efficiency
- Bottleneck identification (CPU, memory, network, Kafka partitions)

**Expected Results**:
- **Linear scaling**: Up to 4 workers (matches 4 partitions)
- **Sub-linear scaling**: Beyond 4 workers (partition-limited)
- **Saturation**: When CPU/memory becomes bottleneck

---

#### Ray Worker Scaling (PRIMARY FOCUS)

**Purpose**: Measure inference throughput improvement with additional Ray workers.

**Test Scenarios**:

1. **Baseline**: 1 Ray worker (1 actor)
   - Measure: Inference throughput, latency
   - Expected: ~10 predictions/sec
   - **Bottleneck**: Single actor processing all inference requests

2. **2 Workers**: 2 Ray workers (2 actors)
   - Measure: Throughput improvement
   - Expected: ~20 predictions/sec (2x improvement)
   - **Bottleneck**: Actor parallelism

3. **4 Workers**: 4 Ray workers (4 actors) (current)
   - Measure: Maximum throughput
   - Expected: ~40 predictions/sec (4x improvement)
   - **Bottleneck**: Matches Spark throughput (optimal)

4. **8 Workers**: Stress test
   - Measure: Saturation point
   - Expected: Diminishing returns (model loading bottleneck or CPU limit)
   - **Note**: More actors may help if inference queue depth is high

**Metrics to Track**:
- Inference throughput scaling
- Latency per actor (should remain constant)
- Actor distribution across workers
- Resource utilization per worker
- Inference queue depth (pending requests)

**Expected Results**:
- **Linear scaling**: Up to 4-8 workers (depending on load)
- **Sub-linear scaling**: Beyond optimal worker count (CPU/memory bottleneck)
- **Saturation**: When model loading or CPU becomes bottleneck

---

#### Kafka Broker Scaling (SECONDARY - For Fault Tolerance)

**Purpose**: Measure impact of multiple Kafka brokers (primarily for fault tolerance, not throughput).

**Important Note**: 
- **Partition count is more important than broker count** for throughput
- **Broker scaling is primarily for**: Fault tolerance (replication), storage capacity
- **Single broker can handle**: 10K-100K+ messages/sec with proper configuration
- **Current setup**: Single broker is sufficient for this workload

**When Kafka Broker Scaling Is Relevant**:
- **Fault tolerance**: Need replication (e.g., replication factor = 3 requires 3+ brokers)
- **Storage capacity**: Single broker disk fills up
- **Very high throughput**: >100K messages/sec (rare for this use case)
- **Geographic distribution**: Multiple data centers

**Test Scenarios** (if needed):

1. **Single Broker**: Current setup
   - Baseline: 1 Kafka broker, 4 partitions
   - Expected: Handles 1000+ msg/sec easily

2. **Multiple Brokers** (if replication needed):
   - 3 Brokers: Replication factor = 3 (fault tolerance)
   - Measure: Throughput impact, fault tolerance
   - Expected: Similar throughput, better fault tolerance

**Metrics to Track** (if testing):
- Throughput with multiple brokers
- Replication lag
- Fault tolerance (broker failure recovery)
- Storage distribution across brokers

**Recommendation**: 
- **For this project**: Focus on Spark/Ray worker scaling
- **Kafka broker scaling**: Only needed if implementing replication for fault tolerance
- **Partition scaling**: More important than broker scaling (see Section 5.3)

---

### 5.2 Load Scaling Tests

**Purpose**: Measure performance with increasing data rates.

**Test Scenarios**:

1. **Low Load**: 1 station, 1 message/second
   - Baseline performance
   - Measure: Latency, resource usage

2. **Medium Load**: 10 stations, 10 messages/second
   - Expected: Linear scaling
   - Measure: Latency increase, resource usage

3. **High Load**: 50 stations, 50 messages/second
   - Expected: Some latency increase
   - Measure: Consumer lag, processing delays

4. **Extreme Load**: 100+ stations, 100+ messages/second
   - Stress test
   - Measure: Saturation point, failure points
   - Identify: Bottlenecks (Kafka, Spark, Ray)

**Metrics to Track**:
- End-to-end latency vs load
- Throughput vs load (should be linear)
- Consumer lag vs load
- Resource utilization vs load
- Failure points (when system breaks)

---

### 5.3 Kafka Partition Scaling Tests (MORE IMPORTANT THAN BROKER SCALING)

**Purpose**: Measure impact of Kafka partition count on parallelism and throughput.

**Why Partition Count Matters More Than Broker Count**:
- **Partitions = Parallelism**: Each partition can be consumed by one consumer thread
- **Direct throughput impact**: More partitions = more parallel Spark tasks = higher throughput
- **Single broker limitation**: A single broker can handle many partitions efficiently
- **Rule of thumb**: Number of partitions should match or exceed number of Spark workers for optimal parallelism

**Data Ingestion for Benchmarks**:

**Current Production Setup**:
- Uses real-time data from NWS API for 5 stations (`src/kafka_weather/producer.py`)
- Fetches data every 15 seconds
- Limited to 5 stations, cannot control rate easily

**Benchmark Approach**:
- **Synthetic Data Generator**: `scripts/benchmark_partition_scaling.py`
- Generates synthetic weather data independently
- **Advantages**:
  - Control message rate (messages per second)
  - Test any number of stations
  - Independent of external API
  - Repeatable and consistent tests
- **Separate Topic**: Uses `weather-raw-benchmark` topic (doesn't interfere with production)

**Test Scenarios**:

1. **2 Partitions**: Half of current
   - Measure: Throughput, partition distribution, Spark task parallelism
   - Expected: Lower throughput (only 2 parallel Spark tasks)
   - **Bottleneck**: Partition count limits Spark parallelism

2. **4 Partitions**: Current setup (OPTIMAL)
   - Baseline
   - Measure: Balanced distribution, optimal parallelism
   - Expected: Matches 4 Spark workers (1 partition per worker)
   - **Optimal**: Partition count = Spark worker count

3. **8 Partitions**: Double partitions
   - Measure: Throughput improvement, Spark task distribution
   - Expected: Better parallelism (8 Spark tasks), but may not improve if only 4 workers
   - **Note**: More partitions than workers may not help much
   - **Use case**: If scaling to 8 Spark workers

**Metrics to Track**:
- Partition distribution balance (messages per partition)
- Throughput per partition
- Consumer lag per partition
- Spark task distribution (tasks per partition)
- Spark worker utilization (are all workers busy?)

**Expected Results**:
- **Optimal**: Partition count = Spark worker count (current: 4 partitions, 4 workers)
- **Under-partitioned**: Fewer partitions than workers (workers idle)
- **Over-partitioned**: More partitions than workers (some partitions underutilized)

**Recommendation**:
- **Current setup (4 partitions, 4 workers)**: Optimal configuration
- **If scaling Spark workers**: Increase partitions proportionally (e.g., 8 workers → 8 partitions)
- **Partition count should match**: Maximum expected Spark worker count

---

#### Running Partition Scaling Benchmarks

**Prerequisites**: 
- ✅ **Docker Compose must be running** (at minimum, Kafka broker)
- ⚠️ Spark/Ray not required for partition distribution tests (only Kafka needed)
- ⚠️ Production producer can continue running (scripts use separate topic)

**See detailed usage guide**: `scripts/README_BENCHMARKS.md`

**Single Test**:
```bash
# From host machine (Kafka on localhost:9092)
python scripts/benchmark_partition_scaling.py --partitions 2 --stations 10 --rate 10 --duration 60

# From Docker container (Kafka on kafka:9092)
docker exec -it kafka python3 /app/scripts/benchmark_partition_scaling.py \
    --partitions 4 --stations 50 --rate 50 --duration 120 \
    --broker kafka:9092
```

**Multiple Tests with Comparison**:
```bash
# From host machine
python scripts/run_partition_scaling_tests.py \
    --partitions 2,4,8 \
    --stations 50 \
    --rate 50 \
    --duration 120 \
    --output partition_scaling_results.json

# From Docker container
docker exec -it kafka python3 /app/scripts/run_partition_scaling_tests.py \
    --partitions 2,4,8 \
    --stations 50 \
    --rate 50 \
    --duration 120 \
    --broker kafka:9092
```

**What the Scripts Do**:
1. **Create benchmark topic** with specified partition count
2. **Generate synthetic weather data** for specified number of stations
3. **Feed data at controlled rate** (messages per second)
4. **Track partition distribution** (which partition each message goes to)
5. **Measure throughput** (actual messages per second)
6. **Calculate balance score** (how evenly distributed across partitions)

**Output**:
- Real-time metrics during test
- Partition distribution table
- Balance score (100% = perfectly balanced)
- Comparison report (if running multiple tests)

---

## 6. Fault Tolerance and Reliability Benchmarks

### 6.1 Component Failure Tests

**Purpose**: Measure system behavior during failures.

**Test Scenarios**:

#### Spark Worker Failure
- **Test**: Kill 1 Spark worker during operation
- **Expected**: 
  - Remaining workers handle load
  - Checkpoint recovery on restart
  - No message loss (Kafka retention)
- **Measure**: Recovery time, data loss, throughput degradation

#### Ray Worker Failure
- **Test**: Kill 1 Ray worker during operation
- **Expected**:
  - Remaining actors handle load
  - Actor recreation on restart
  - Temporary throughput reduction
- **Measure**: Recovery time, actor recreation time, message loss

#### Kafka Broker Failure
- **Test**: Restart Kafka broker
- **Expected**:
  - Producers/consumers reconnect
  - No message loss (if replication enabled)
  - Temporary processing pause
- **Measure**: Reconnection time, message loss, recovery time

#### Spark Master Failure
- **Test**: Restart Spark master
- **Expected**:
  - Workers reconnect
  - Streaming job restarts from checkpoint
  - No data loss (checkpoint recovery)
- **Measure**: Recovery time, checkpoint read time

---

### 6.2 Data Loss Tests

**Metrics**:

- **Message Loss Rate**: Lost messages / total messages
  - Target: 0% (with proper Kafka retention and checkpointing)
  - Test: Kill components, measure message loss

- **Checkpoint Integrity**: Successful checkpoint recoveries / total recoveries
  - Target: 100%
  - Test: Restart Spark, verify checkpoint recovery

- **Duplicate Messages**: Duplicate predictions / total predictions
  - Target: < 0.1% (idempotent processing)
  - Monitor: Duplicate detection in API

---

### 6.3 Recovery Time Tests

**Metrics**:

- **Spark Recovery Time**: Time from restart → first batch processed
  - Target: < 30 seconds
  - Measurement: Checkpoint read + worker reconnection + first batch

- **Ray Recovery Time**: Time from restart → actors ready
  - Target: < 20 seconds
  - Measurement: Worker reconnection + actor creation + model loading

- **End-to-End Recovery**: Time from failure → pipeline operational
  - Target: < 1 minute
  - Measurement: All components recovered and processing

---

## 7. Resource Utilization Benchmarks

### 7.1 CPU Utilization

**Metrics**:

- **Per-Container CPU Usage**: CPU % per container
  - Kafka: Target < 60% (I/O bound)
  - Spark Master: Target < 40% (coordination)
  - Spark Workers: Target 60-80% (processing)
  - Ray Head: Target < 40% (coordination)
  - Ray Workers: Target 60-80% (inference)
  - API: Target < 50% (serving)

- **Total CPU Usage**: Sum across all containers
  - Current: 13.5 CPU cores allocated
  - Target: < 80% average utilization
  - Alert: > 90% indicates CPU bottleneck

**Tools**: `docker stats`, `htop`, Prometheus

---

### 7.2 Memory Utilization

**Metrics**:

- **Per-Container Memory Usage**: RAM usage per container
  - Kafka: Target < 1.5GB / 2GB (75%)
  - Spark Master: Target < 1.5GB / 2GB (75%)
  - Spark Workers: Target < 2.5GB / 3GB (83%)
  - Ray Head: Target < 2.5GB / 3GB (83%)
  - Ray Workers: Target < 2.5GB / 3GB (83%)
  - API: Target < 1.5GB / 2GB (75%)

- **Total Memory Usage**: Sum across all containers
  - Current: 35GB allocated
  - Target: < 85% average utilization
  - Alert: > 90% indicates memory pressure

- **Memory Leaks**: Growing memory over time
  - Monitor: Memory usage trends (24+ hours)
  - Alert: Continuous growth indicates leak

**Tools**: `docker stats`, `free -h`, Prometheus

---

### 7.3 Network Utilization

**Metrics**:

- **Inter-Container Traffic**: Bytes/sec between containers
  - Kafka ↔ Spark: Producer/consumer traffic
  - Spark ↔ Kafka: Feature output
  - Kafka ↔ Ray: Feature consumption
  - Ray ↔ Kafka: Prediction output
  - Target: Monitor for bottlenecks

- **Network Latency**: Ping time between containers
  - Target: < 1ms (same Docker network)
  - Alert: > 10ms indicates network issues

**Tools**: `docker stats`, `iftop`, `ping`

---

### 7.4 Disk Utilization

**Metrics**:

- **Kafka Log Size**: Size of Kafka topic logs
  - Monitor: `weather-raw`, `weather-features`, `weather-predictions`
  - Target: < 10GB per topic (with retention)
  - Alert: Rapid growth indicates consumer lag

- **Spark Checkpoint Size**: Size of checkpoint directory
  - Monitor: Checkpoint directory growth
  - Target: < 5GB
  - Alert: Continuous growth indicates state store issues

- **Model Storage Size**: Size of model files
  - Monitor: `/app/models` directory
  - Target: < 1GB per model

**Tools**: `du -sh`, `df -h`, Docker volume inspection

---

## 8. Benchmark Implementation Plan

### Phase 1: Basic Metrics Collection ⏳

**Tasks**:
- [ ] Add timestamps to all pipeline stages
- [ ] Implement Kafka consumer lag monitoring
- [ ] Add Spark batch processing time logging
- [ ] Add Ray inference latency tracking
- [ ] Create basic metrics collection script

**Tools**: Custom Python scripts, Kafka admin tools, Spark UI, Ray Dashboard

---

### Phase 2: Automated Benchmark Suite ⏳

**Tasks**:
- [ ] Create `scripts/benchmark_system.py` script
- [ ] Implement latency measurement tools
- [ ] Implement throughput measurement tools
- [ ] Create scalability test scripts
- [ ] Generate benchmark reports

**Script Structure**:
```bash
scripts/
├── benchmark_system.py          # Main benchmark runner
├── benchmark_latency.py         # Latency measurements
├── benchmark_throughput.py     # Throughput measurements
├── benchmark_scalability.py    # Scaling tests
└── benchmark_resources.py      # Resource monitoring
```

---

### Phase 3: Monitoring Dashboard ⏳

**Tasks**:
- [ ] Set up Prometheus for metrics collection
- [ ] Create Grafana dashboards
- [ ] Add real-time monitoring
- [ ] Create alerting rules

**Dashboards**:
- Kafka metrics (consumer lag, throughput)
- Spark metrics (batch time, processing delay)
- Ray metrics (actor performance, inference latency)
- System resources (CPU, memory, network)

---

### Phase 4: Continuous Benchmarking ⏳

**Tasks**:
- [ ] Integrate benchmarks into CI/CD
- [ ] Automated performance regression detection
- [ ] Benchmark result storage and comparison
- [ ] Performance trend analysis

---

## 9. Benchmark Execution Examples

### Running Latency Benchmarks
```bash
# Measure end-to-end latency
python scripts/benchmark_system.py --test latency --duration 300

# Measure component-level latency
python scripts/benchmark_system.py --test latency --component kafka
python scripts/benchmark_system.py --test latency --component spark
python scripts/benchmark_system.py --test latency --component ray
```

### Running Throughput Benchmarks
```bash
# Measure throughput with different loads
python scripts/benchmark_system.py --test throughput --stations 1 --duration 60
python scripts/benchmark_system.py --test throughput --stations 10 --duration 60
python scripts/benchmark_system.py --test throughput --stations 100 --duration 60
```

### Running Scalability Benchmarks
```bash
# Test Spark worker scaling
python scripts/benchmark_system.py --test scalability --component spark --workers 1,2,4,8

# Test Ray worker scaling
python scripts/benchmark_system.py --test scalability --component ray --workers 1,2,4,8

# Test load scaling
python scripts/benchmark_system.py --test scalability --load 1,10,50,100
```

### Running Resource Benchmarks
```bash
# Monitor resource usage
python scripts/benchmark_system.py --test resources --duration 600

# Monitor specific component
python scripts/benchmark_system.py --test resources --component kafka
```

### Running Fault Tolerance Benchmarks
```bash
# Test Spark worker failure
python scripts/benchmark_system.py --test fault-tolerance --component spark-worker1

# Test Ray worker failure
python scripts/benchmark_system.py --test fault-tolerance --component ray-worker1

# Test recovery time
python scripts/benchmark_system.py --test recovery --component spark
```

---

## 10. Benchmark Targets Summary

| Metric | Target | Critical Threshold | Current Status |
|--------|--------|-------------------|----------------|
| **End-to-End Latency** | < 1 minute | > 2 minutes | ⏳ To Measure |
| **Producer Latency** | < 100ms | > 500ms | ⏳ To Measure |
| **Spark Processing Time** | < 5 seconds | > 10 seconds | ⏳ To Measure |
| **Ray Inference Latency** | < 100ms | > 500ms | ⏳ To Measure |
| **System Throughput** | 1000+ msg/sec | < 100 msg/sec | ⏳ To Measure |
| **Kafka Consumer Lag (Spark)** | < 1000 msgs | > 10,000 msgs | ⏳ To Measure |
| **Kafka Consumer Lag (Ray)** | < 500 msgs | > 5,000 msgs | ⏳ To Measure |
| **Spark Batch Processing Time** | < batch interval | > 2x batch interval | ⏳ To Measure |
| **Ray Actor Startup Time** | < 5 seconds | > 10 seconds | ⏳ To Measure |
| **CPU Utilization** | < 80% | > 90% | ⏳ To Measure |
| **Memory Utilization** | < 85% | > 90% | ⏳ To Measure |
| **Recovery Time** | < 1 minute | > 5 minutes | ⏳ To Measure |
| **Message Loss Rate** | 0% | > 0.1% | ⏳ To Measure |

---

## 11. Recommended Tools

### For Kafka Monitoring
- **Kafka Admin Tools**: `kafka-consumer-groups.sh`, `kafka-topics.sh`
- **Kafka JMX Metrics**: Consumer lag, throughput, partition distribution
- **Kafdrop** (optional): Web UI for Kafka topics

### For Spark Monitoring
- **Spark UI**: http://localhost:8080 (built-in)
- **Spark Metrics API**: Programmatic access to metrics
- **Spark History Server**: For historical metrics (if enabled)

### For Ray Monitoring
- **Ray Dashboard**: http://localhost:8265 (built-in)
- **Ray Metrics API**: Programmatic access to metrics
- **Ray Logs**: Actor logs and errors

### For System Monitoring
- **Docker Stats**: `docker stats` for container resources
- **Prometheus + Grafana**: Comprehensive metrics collection and visualization
- **cAdvisor**: Container resource monitoring (optional)

### For Load Testing
- **Custom Scripts**: Python scripts to generate load
- **Locust**: HTTP load testing (for API)
- **Kafka Producer Performance**: Built-in Kafka tools

---

## 12. Next Steps

1. **Implement Basic Metrics Collection**
   - Add timestamps to pipeline stages
   - Create metrics collection scripts
   - Set up basic monitoring

2. **Create Benchmark Suite**
   - Implement `benchmark_system.py`
   - Add latency, throughput, scalability tests
   - Generate benchmark reports

3. **Set Up Monitoring**
   - Deploy Prometheus + Grafana
   - Create dashboards for each component
   - Set up alerting

4. **Run Baseline Benchmarks**
   - Measure current performance
   - Establish baseline metrics
   - Document current capabilities

5. **Optimize Based on Results**
   - Identify bottlenecks
   - Tune configurations
   - Re-run benchmarks to verify improvements

---

## References

- Architecture: `Documentation/architecture.md`
- Design: `Documentation/improved_design.md`
- Docker Compose: `docker-compose.yml`
- Kafka Documentation: https://kafka.apache.org/documentation/
- Spark Streaming Guide: https://spark.apache.org/docs/latest/streaming-programming-guide.html
- Ray Documentation: https://docs.ray.io/
