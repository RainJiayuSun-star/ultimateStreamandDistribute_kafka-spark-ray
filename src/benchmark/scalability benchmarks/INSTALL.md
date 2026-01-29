# Installation Guide

## Quick Fix for "ModuleNotFoundError: No module named 'kafka'"

### From Host Machine

```bash
# Install dependencies
pip install -r benchmark/scalability\ benchmarks/requirements.txt

# Or install individually
pip install kafka-python matplotlib seaborn numpy requests
```

### Verify Installation

```bash
python3 -c "import kafka; print('kafka-python:', kafka.__version__)"
python3 -c "import matplotlib; print('matplotlib:', matplotlib.__version__)"
python3 -c "import seaborn; print('seaborn:', seaborn.__version__)"
```

## Running from Docker Container

The benchmark directory is **not mounted by default** in docker-compose.yml. You have two options:

### Option 1: Copy Scripts to Mounted Directory (Quick Fix)

```bash
# Copy benchmark scripts to src directory (which IS mounted)
cp -r benchmark/scalability\ benchmarks src/benchmark_scalability

# Run from container
docker exec -it kafka python3 /app/src/benchmark_scalability/scalability_benchmark.py \
    --test all --duration 300 --broker kafka:9092
```

### Option 2: Mount Benchmark Directory (Permanent Fix)

Edit `docker-compose.yml` and add benchmark directory to Kafka container volumes:

```yaml
kafka:
  # ... other config ...
  volumes:
    - ./src:/app/src:ro
    - ./benchmark:/app/benchmark:ro  # Add this line
```

Then restart:
```bash
docker compose down
docker compose up -d
```

Now you can run:
```bash
docker exec -it kafka python3 /app/benchmark/scalability\ benchmarks/scalability_benchmark.py \
    --test all --duration 300 --broker kafka:9092
```

## Recommended Approach

**Run from host machine** - it's simpler and doesn't require Docker volume changes:

```bash
# 1. Install dependencies
pip install -r benchmark/scalability\ benchmarks/requirements.txt

# 2. Ensure Docker Compose is running
docker compose up -d

# 3. Run benchmarks
python benchmark/scalability\ benchmarks/scalability_benchmark.py --test all --duration 300

# Or use the helper script
bash benchmark/scalability\ benchmarks/run_from_host.sh --test all --duration 300
```
