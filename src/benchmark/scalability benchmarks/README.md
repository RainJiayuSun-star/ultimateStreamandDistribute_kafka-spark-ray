# Scalability Benchmarks

This directory contains benchmark scripts for testing scalability of the Kafka-Spark-Ray pipeline.

## Overview

The scalability benchmarks test three main aspects:

1. **Horizontal Scaling**: Performance with different numbers of Spark/Ray workers
2. **Load Scaling**: Performance with different message rates (load levels)
3. **Partition Scaling**: Performance with different Kafka partition counts

## Prerequisites

**YES - Docker Compose MUST be running!**

### Required Services (Minimum)
- ✅ **Kafka broker** (REQUIRED) - For creating topics, sending messages, checking consumer lag
- ✅ **Docker** (REQUIRED) - For collecting resource usage metrics via `docker stats`

### Optional Services (Recommended)
- ⚠️ **Spark** (OPTIONAL but recommended) - For measuring Spark consumer lag and processing metrics
- ⚠️ **Ray** (OPTIONAL but recommended) - For measuring Ray consumer lag and inference metrics

### Python Packages Required
- `kafka-python`
- `matplotlib`
- `seaborn`
- `numpy`
- `requests`

## Quick Start

### Option 1: Run from Host Machine (Recommended)

```bash
# 1. Install Python dependencies
pip install -r benchmark/scalability\ benchmarks/requirements.txt

# 2. Start Docker Compose (if not already running)
docker compose up -d

# 3. Wait for services to be ready (~30 seconds)
docker compose ps

# 4. Run benchmarks
python benchmark/scalability\ benchmarks/scalability_benchmark.py --test all --duration 300
```

### Option 2: Run from Docker Container

**Note**: The benchmark directory needs to be mounted. Currently only `./src` is mounted.

**Option A**: Copy scripts to src directory (temporary):
```bash
# Copy benchmark scripts to src (which is mounted)
cp -r benchmark/scalability\ benchmarks src/benchmark_scalability

# Run from container
docker exec -it kafka python3 /app/src/benchmark_scalability/scalability_benchmark.py \
    --test all --duration 300 --broker kafka:9092
```

**Option B**: Mount benchmark directory (modify docker-compose.yml):
Add to Kafka container volumes:
```yaml
volumes:
  - ./src:/app/src:ro
  - ./benchmark:/app/benchmark:ro  # Add this line
```

Then run:
```bash
docker exec -it kafka python3 /app/benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test all --duration 300 --broker kafka:9092
```

## Usage

### Run All Tests

```bash
# From project root
python benchmark/scalability\ benchmarks/scalability_benchmark.py --test all --duration 300
```

### Run Specific Tests

**Horizontal Scaling**:
```bash
python benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test horizontal \
    --workers 1,2,4,8 \
    --duration 300
```

**Load Scaling**:
```bash
python benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test load \
    --rates 1,10,50,100 \
    --stations 50 \
    --duration 300
```

**Partition Scaling**:
```bash
python benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test partition \
    --partitions 2,4,8 \
    --stations 50 \
    --duration 300
```

### From Docker Container

```bash
# Run inside Kafka container
docker exec -it kafka python3 /app/benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test all \
    --duration 300 \
    --broker kafka:9092
```

## Output

**When running from host**:
Results are saved to `src/benchmark/scalability benchmarks/output/results_<timestamp>/`

**When running from Docker**:
Results are saved to `/tmp/benchmark_results/results_<timestamp>/` (since `/app/src` is mounted read-only)

**To copy results from Docker to host**:
```bash
docker cp kafka:/tmp/benchmark_results ./benchmark_results_from_docker
```

**Results include**:
- `all_results.json` - Complete benchmark results
- `horizontal_scaling_results.json` - Horizontal scaling test results
- `load_scaling_results.json` - Load scaling test results
- `partition_scaling_results.json` - Partition scaling test results
- `horizontal_scaling_results.png` - Visualization graphs (if matplotlib available)
- `load_scaling_results.png` - Visualization graphs (if matplotlib available)
- `partition_scaling_results.png` - Visualization graphs (if matplotlib available)

## Test Details

### Horizontal Scaling Tests

Tests performance with different numbers of workers:
- Measures throughput scaling
- Tracks consumer lag
- Monitors resource utilization
- Calculates scaling efficiency

**Note**: Requires manual scaling of workers in docker-compose.yml or dynamic scaling support.

### Load Scaling Tests

Tests performance under different load levels:
- Generates synthetic data at controlled rates
- Measures consumer lag vs load
- Tracks error rates
- Identifies saturation points

### Partition Scaling Tests

Tests performance with different Kafka partition counts:
- Measures throughput vs partitions
- Calculates partition balance scores
- Tracks consumer lag
- Identifies optimal partition count

## Visualization

Graphs are automatically generated showing:
- Throughput scaling
- Consumer lag trends
- Resource utilization
- Scaling efficiency
- Error rates

## Customization

Edit the benchmark scripts to:
- Adjust test parameters
- Add custom metrics
- Modify visualization styles
- Add additional test scenarios

## Troubleshooting

### "ModuleNotFoundError: No module named 'kafka'"

**Problem**: Python dependencies not installed

**Solution**:
```bash
# Install dependencies
pip install -r benchmark/scalability\ benchmarks/requirements.txt

# Or use the helper script
bash benchmark/scalability\ benchmarks/run_from_host.sh --test all --duration 300
```

### "NoBrokersAvailable" Error

**Problem**: Cannot connect to Kafka

**Solutions**:
- ✅ **Ensure Docker Compose is running**: `docker compose ps`
- ✅ **Check Kafka is accessible**: `docker compose logs kafka`
- ✅ **Wait for Kafka to fully start**: Takes ~30 seconds after `docker compose up`
- ✅ **Verify broker address**: Use `localhost:9092` from host or `kafka:9092` from Docker

### "File not found" when running from Docker

**Problem**: Benchmark directory not mounted in Docker container

**Solutions**:

**Option 1**: Run from host (recommended)
```bash
pip install -r benchmark/scalability\ benchmarks/requirements.txt
python benchmark/scalability\ benchmarks/scalability_benchmark.py --test all
```

**Option 2**: Copy scripts to mounted directory
```bash
# Copy to src (which is mounted)
cp -r benchmark/scalability\ benchmarks src/benchmark_scalability

# Run from container
docker exec -it kafka python3 /app/src/benchmark_scalability/scalability_benchmark.py \
    --test all --broker kafka:9092
```

**Option 3**: Mount benchmark directory in docker-compose.yml
Add to Kafka container volumes section:
```yaml
volumes:
  - ./src:/app/src:ro
  - ./benchmark:/app/benchmark:ro  # Add this
```

### "Docker stats failed" Error

**Problem**: Cannot collect resource metrics

**Solutions**:
- ✅ **Ensure Docker is running**: `docker ps`
- ✅ **Check container names**: Containers must match expected names (kafka, spark-worker1, etc.)
- ⚠️ **This is non-fatal**: Benchmarks will continue with limited metrics

### "Cannot connect to Spark UI" Warning

**Problem**: Spark metrics unavailable

**Note**: This is OK - Spark metrics are optional
- Benchmarks will still work using Kafka consumer lag metrics
- To enable: Ensure Spark is running and accessible at http://localhost:8080

**Low Throughput**:
- Check system resources (CPU, memory)
- Verify Spark/Ray workers are running
- Check for consumer lag accumulation

**Missing Metrics**:
- Ensure Spark UI is accessible (http://localhost:8080)
- Ensure Ray Dashboard is accessible (http://localhost:8265)
- Check Docker containers are running

## Files

- `scalability_benchmark.py` - Main benchmark runner
- `metrics_collector.py` - Metrics collection from Kafka/Spark/Ray
- `horizontal_scaling.py` - Horizontal scaling test implementation
- `load_scaling.py` - Load scaling test implementation
- `partition_scaling.py` - Partition scaling test implementation
- `visualization.py` - Graph generation
