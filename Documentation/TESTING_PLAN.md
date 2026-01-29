# Manual Configuration and Testing Plan

This document describes how to manually test the Kafka-Spark-Ray pipeline with different input volumes/rates and different worker/partition counts. No automation changes worker count; you change config and restart, then run the scalability benchmarks.

---

## 1. Summary

**Purpose:** Manually test system efficiency with:

- **Different numbers and sizes of inputs:** Message rate (msg/sec), number of synthetic stations, and test duration—controlled via the benchmark CLI.
- **Different numbers of workers per system:** Kafka partition count, Spark worker count, Ray worker count, and Ray inference actor count—controlled by editing config files and `docker-compose.yml`, then restarting services.

**Benchmark suite:** The scalability benchmarks live in `src/benchmark/scalability benchmarks/` and support horizontal scaling, load scaling, and partition scaling tests. See [src/benchmark/scalability benchmarks/README.md](../src/benchmark/scalability%20benchmarks/README.md) for prerequisites and quick start.

---

## 2. Config Reference (What to Change)

| Goal | File(s) to configure | What to change | Notes |
|------|---------------------|----------------|-------|
| **Kafka partition count** | `src/kafka_weather/producer.py` | `TOPICS` (lines 24–28): set `"partitions": N` for each topic. Optionally keep `src/utils/kafka_config.py` `TOPIC_PARTITIONS` in sync. | Only affects **new** topic creation. Existing topics keep their partition count; delete and recreate topics (or use benchmark-created topics with different names) to test different partition counts. |
| **Spark worker count** | `docker-compose.yml` | Number of `spark-worker*` services (e.g. comment out `spark-worker3` and `spark-worker4` to test with 2 workers). | After editing: `docker compose down` then `docker compose up -d`. |
| **Ray worker count** | `docker-compose.yml` | Number of `ray-worker*` services (e.g. comment out `ray-worker3` and `ray-worker4` to test with 2 workers). | After editing: `docker compose down` then `docker compose up -d`. |
| **Ray inference actor count** | `docker-compose.yml` and/or `src/ray/inference/ray_consumer.py` | **Option A:** Override `ray-inference` command to pass `--num-actors N`. **Option B:** Set env `RAY_NUM_ACTORS=N` in docker-compose under `ray-inference` (the code reads this env; default is 4). | Restart `ray-inference` (or full stack) after change. |
| **Input rate / size** | None (benchmark CLI) | Use `--rates`, `--stations`, `--duration` when running `scalability_benchmark.py`. | No config file edits. |

---

## 3. Step-by-Step: Changing Spark Worker Count

1. **Edit `docker-compose.yml`**
   - Locate the Spark worker services: `spark-worker1` … `spark-worker4` (around lines 77–176).
   - Comment out the full service blocks for the workers you want to remove (e.g. `spark-worker3` and `spark-worker4` for a 2-worker test).

2. **Restart the stack**
   ```bash
   docker compose down
   docker compose up -d
   ```

3. **Wait for services**
   - Wait until Spark master and workers are healthy (e.g. Spark UI at http://localhost:8080 shows the desired number of workers).

4. **Run the benchmark**
   ```bash
   python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test horizontal --workers 2 --duration 300
   ```
   (Use the same worker count as in docker-compose for consistency.)

5. **Save or note the output directory**
   - Results go to `src/benchmark/scalability benchmarks/output/results_YYYYMMDD_HHMMSS/` (or `/tmp/benchmark_results` when run inside a container).

6. **Restore for next test**
   - Uncomment the worker services in `docker-compose.yml`, then `docker compose down` and `docker compose up -d` again.

---

## 4. Step-by-Step: Changing Ray Worker Count

1. **Edit `docker-compose.yml`**
   - Locate `ray-worker1` … `ray-worker4` (around lines 233–326).
   - Comment out the full service blocks for the workers you want to remove (e.g. `ray-worker3` and `ray-worker4` for a 2-worker test).

2. **Restart the stack**
   ```bash
   docker compose down
   docker compose up -d
   ```

3. **Wait for Ray**
   - Wait until Ray head and workers are ready (e.g. Ray Dashboard at http://localhost:8265).

4. **Run the benchmark**
   ```bash
   python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test horizontal --workers 2 --duration 300
   ```

5. **Note results directory** (same as in section 3).

6. **Restore** by uncommenting Ray worker services and restarting.

---

## 5. Step-by-Step: Changing Ray Actor Count

1. **Edit `docker-compose.yml`**
   - Find the `ray-inference` service (around line 328).
   - **Option A (command override):** Change the `command` to pass `--num-actors N`, e.g.:
     ```yaml
     command: >
       sh -c "sleep 60 && python3 /app/src/ray/inference/ray_consumer.py --num-actors 2"
     ```
   - **Option B (env var):** Set under `ray-inference` `environment:` in docker-compose (the code reads `RAY_NUM_ACTORS`):
     ```yaml
     - RAY_NUM_ACTORS=2
     ```

2. **Restart ray-inference (or full stack)**
   ```bash
   docker compose up -d ray-inference
   ```
   or `docker compose down` then `docker compose up -d` for a full restart.

3. **Run the benchmark** (e.g. horizontal or load test).

4. **Restore** the original command or env when done.

---

## 6. Step-by-Step: Kafka Partition Count

1. **Edit `src/kafka_weather/producer.py`**
   - In `TOPICS` (lines 24–28), set `"partitions": N` (e.g. 2, 4, or 8) for the topics you use in the benchmark.

2. **Recreate topics**
   - Kafka does not allow changing partition count on existing topics. Either:
     - Delete the existing topics (e.g. via Kafka tooling or admin client), then run the producer or whatever script creates topics so they are created with the new partition count; or
     - Use a benchmark that creates its own topics with the desired partition count (e.g. load benchmark uses `weather-raw-load-test`; partition scaling would need a script that creates a topic with N partitions).
   - **Note:** The partition-scaling benchmark currently expects a script `scripts/benchmark_partition_scaling.py` that does not exist. Until that script is added, partition tests can be done manually: change `TOPICS` in producer, delete/recreate the main topics, then run the load benchmark, or add a small script that creates a topic with N partitions, produces at a fixed rate, and collects lag/throughput.

3. **Run the benchmark** (load or partition test).

4. **Restore** `TOPICS` and recreate topics if you need the original partition count for other tests.

---

## 7. Benchmark Matrix (Suggested Runs)

Use these as a checklist. For each row, apply the config changes, restart if needed, run the listed benchmark command, and note the results directory.

| Test type | Config to set | Benchmark command | Results location |
|-----------|----------------|--------------------|------------------|
| **Baseline** | 4 partitions, 4 Spark workers, 4 Ray workers, 4 Ray actors | `--test all --duration 300` (or start with `--test load --rates 10`) | `src/benchmark/scalability benchmarks/output/results_<timestamp>/` |
| **Load scaling** | Same as baseline | `--test load --rates 1,10,50,100 --duration 300` | Same |
| **Spark workers** | docker-compose: 1 worker (comment out worker2–4), then 2, then 4 | `--test horizontal --workers 1` then `--workers 2` then `--workers 4`; run after each config change | Same |
| **Ray workers** | docker-compose: 1 Ray worker, then 2, then 4 | `--test horizontal --workers 1` then `2` then `4`; run after each config change | Same |
| **Ray actors** | docker-compose: ray-inference with `--num-actors 2`, then 4 | `--test load --rates 10,50 --duration 300` (or horizontal) | Same |
| **Partitions** | producer.py TOPICS partitions = 2, then 4, then 8; recreate topics each time | Manual load test or add `scripts/benchmark_partition_scaling.py` and run `--test partition --partitions 2,4,8` | Same |

---

## 8. Running the Benchmarks

**Prerequisites:**

- Docker Compose is up: `docker compose up -d`
- Kafka is healthy (and optionally Spark and Ray if you are testing those).
- Python dependencies for the benchmark:  
  `pip install -r "src/benchmark/scalability benchmarks/requirements.txt"`

**From repo root:**

```bash
# All tests (horizontal + load + partition)
python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test all --duration 300

# Only load scaling
python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test load --rates 1,10,50,100 --duration 300

# Only horizontal scaling (measures current worker config; change workers in docker-compose first)
python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test horizontal --workers 1,2,4 --duration 300

# Only partition scaling (requires scripts/benchmark_partition_scaling.py or manual topic setup)
python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test partition --partitions 2,4,8 --duration 300
```

For running **inside a Docker container** (e.g. with broker `kafka:9092`), see [src/benchmark/scalability benchmarks/README.md](../src/benchmark/scalability%20benchmarks/README.md).

---

## 9. Where Results Go

- **Default (run from host):**  
  `src/benchmark/scalability benchmarks/output/results_<timestamp>/`

- **When run inside Docker:**  
  `/tmp/benchmark_results` (or the path set by `--output`).

**Files in each results directory:**

- `all_results.json` – Combined results for all test types run.
- `horizontal_scaling_results.json` – Horizontal scaling metrics.
- `load_scaling_results.json` – Load scaling metrics.
- `partition_scaling_results.json` – Partition scaling metrics (if partition test ran).
- `*_results.png` – Plots (if visualization was not disabled with `--no-viz`).

Use these to compare throughput, consumer lag, and resource usage across different configurations.

---

## 10. Partition Scaling Note

Partition scaling in the benchmark suite calls `scripts/benchmark_partition_scaling.py`, which is **not** present in the repo. Options:

- **Add the script:** Implement a script that creates a topic with N partitions, produces at a fixed rate for a given duration, and collects consumer lag/throughput (and optionally calls the metrics collector), then have the partition-scaling benchmark invoke it.
- **Manual procedure:** Follow section 6: set `TOPICS[].partitions` in `producer.py`, delete/recreate topics, run the load benchmark or a custom producer at fixed rate, and collect metrics manually or via the existing metrics collector.

Once the script exists or a manual procedure is fixed, document the exact steps in this section or in the benchmark README.
