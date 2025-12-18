# Testers Directory

This directory contains test/consumer scripts to verify the data pipeline is working correctly.

## Available Testers

### 1. `debug_consumer.py` - Raw Weather Data Consumer

**Purpose:** Consumes and displays raw weather data from the `weather-raw` Kafka topic. This verifies that the producer is correctly fetching and publishing weather data to Kafka.

**What it does:**
- Connects to Kafka and subscribes to the `weather-raw` topic
- Consumes messages in real-time
- Prints formatted dictionaries showing raw weather observations
- Displays: station_id, station_name, timestamp, temperature, humidity, wind_speed, wind_direction, sea_level_pressure, precipitation, and partition number

**Prerequisites:**
- Kafka container must be running
- Producer must be running and sending data to `weather-raw` topic

**How to Run:**

**Option A: Run in Docker (Recommended)**
```bash
docker exec -it kafka python3 /app/src/testers/debug_consumer.py
```

**Option B: Run Locally (if Kafka is accessible from host)**
```bash
python3 src/testers/debug_consumer.py
```

**Expected Output:**
```
Waiting for partition assignment...
Consumer assigned to partitions: {TopicPartition(topic='weather-raw', partition=0), ...}
Starting to consume messages from topic 'weather-raw'...
================================================================================
{'station_id': 'KMSN', 'station_name': 'Madison', 'timestamp': '2025-12-13T05:30:00Z', 
 'temperature': 45.2, 'humidity': 65.5, 'wind_speed': 10.3, 'wind_direction': 180, 
 'sea_level_pressure': 1013.25, 'precipitation_last_hour': 0.0, 'partition': 0}
...
```

**To Stop:** Press `Ctrl+C`

---

### 2. `test_spark_features.py` - Spark Aggregated Features Consumer

**Purpose:** Consumes and displays aggregated weather features from the `weather-features` Kafka topic. This verifies that Spark streaming is correctly processing raw data, performing windowed aggregations, and writing results to Kafka.

**What it does:**
- Connects to Kafka and subscribes to the `weather-features` topic
- Consumes messages containing aggregated features produced by Spark
- Prints formatted JSON showing:
  - Window timestamps (start/end)
  - Temperature statistics (mean, std, min, max)
  - Humidity statistics (mean, std, min, max)
  - Pressure statistics (mean, std, min, max)
  - Wind statistics (speed mean/std/min/max, direction mean)
  - Precipitation statistics (mean, max)
  - Measurement count per window

**Prerequisites:**
- Kafka container must be running
- Spark streaming application must be running
- Producer must be sending data (so Spark has data to process)
- Wait at least 1-2 minutes after starting Spark for first batch to complete

**How to Run:**

**Option A: Run in Docker (Recommended)**
```bash
docker exec -it spark-master python3 /app/src/testers/test_spark_features.py
```

**Option B: Run Locally (if Kafka is accessible from host)**
```bash
python3 src/testers/test_spark_features.py
```

**Expected Output:**
```
Waiting for partition assignment...
Consumer assigned to partitions: {TopicPartition(topic='weather-features', partition=0), ...}
Starting to consume aggregated features from topic 'weather-features'...
================================================================================
Expected format: Aggregated features with window_start, window_end, and statistics
================================================================================

--- Message #1 ---
{
  "station_id": "KMSN",
  "partition": 0,
  "window_start": "2025-12-13 05:30:00",
  "window_end": "2025-12-13 05:35:00",
  "measurement_count": 15,
  "temperature_stats": {
    "mean": 45.2,
    "std": 2.1,
    "min": 42.0,
    "max": 48.5
  },
  "humidity_stats": {
    "mean": 65.5,
    "std": 3.2,
    "min": 60.0,
    "max": 70.0
  },
  ...
}
```

**To Stop:** Press `Ctrl+C`

**Note:** This tester uses `auto_offset_reset='earliest'` by default, so it will show **all historical messages** from the beginning of the topic. If you want to see only new messages, change `OFFSET_STRATEGY = 'latest'` in the script.

---

## Quick Test Sequence

To verify the entire pipeline is working:

1. **Check Producer (Raw Data):**
   ```bash
   docker exec -it kafka python3 /app/src/testers/debug_consumer.py
   ```
   You should see raw weather data messages appearing every 15 seconds.

2. **Check Spark Processing (Aggregated Features):**
   ```bash
   # First, ensure Spark streaming is running:
   docker exec -d spark-master spark-submit \
     --master spark://spark-master:7077 \
     --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.7 \
     /app/src/spark/streaming_app.py
   
   # Wait 1-2 minutes for Spark to process first batch
   # Then run the tester:
   docker exec -it spark-master python3 /app/src/testers/test_spark_features.py
   ```
   You should see aggregated features with statistics.

---

## Troubleshooting

### No Output from `debug_consumer.py`

**Possible Causes:**
- Producer is not running: Check with `docker logs kafka | grep "Published"`
- No messages in topic: Check with `docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic weather-raw`
- Consumer is using `auto_offset_reset='latest'` and no new messages are arriving

**Solutions:**
- Verify producer is running: `docker ps | grep kafka`
- Check producer logs: `docker logs kafka | tail -20`
- Wait for producer to send next batch (every 15 seconds)

### No Output from `test_spark_features.py`

**Possible Causes:**
- Spark streaming is not running: Check with `docker exec spark-master ps aux | grep streaming_app`
- Spark hasn't processed any batches yet (wait 1-2 minutes)
- No data in `weather-raw` topic for Spark to process
- Spark encountered an error: Check Spark logs

**Solutions:**
- Verify Spark is running: `docker exec spark-master ps aux | grep streaming`
- Check Spark UI: Open `http://localhost:8080` in browser
- Check if `weather-features` topic has messages:
  ```bash
  docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \
    kafka.tools.GetOffsetShell \
    --broker-list localhost:9092 \
    --topic weather-features
  ```
- Check Spark logs: `docker logs spark-master | tail -50`
- Verify consumer group exists:
  ```bash
  docker exec kafka /kafka_2.12-3.6.2/bin/kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --group spark-streaming-group \
    --describe
  ```

### Connection Errors

**Error: `NoBrokersAvailable`**
- Kafka container is not running: `docker ps | grep kafka`
- Kafka is not ready yet: Wait a few seconds and try again
- Network issue: Verify containers are on the same Docker network

**Error: `Connection refused`**
- Kafka is not listening on port 9092
- Check Kafka logs: `docker logs kafka | tail -20`

---

## Configuration

Both testers use the following configuration (can be modified in the scripts):

- **Broker:** `kafka:9092` (Docker) or `localhost:9092` (local)
- **Consumer Group:** 
  - `debug_consumer.py`: `debug`
  - `test_spark_features.py`: `spark-features-test`
- **Auto Offset Reset:** `latest` (only new messages)
- **Auto Commit:** `True`

To read from the beginning of the topic, change `auto_offset_reset='latest'` to `auto_offset_reset='earliest'` in the respective script.

---

## Additional Verification Commands

### Check Topic Message Counts
```bash
# Check weather-raw topic
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \
  kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic weather-raw

# Check weather-features topic
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \
  kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic weather-features
```

### Check Consumer Groups
```bash
# List all consumer groups
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list

# Check Spark consumer group status
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group spark-streaming-group \
  --describe
```

### View Raw Messages (One-time)
```bash
# View one message from weather-raw
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw \
  --from-beginning \
  --max-messages 1

# View one message from weather-features
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-features \
  --from-beginning \
  --max-messages 1
```

---

### 3. `test_data_collector.py` - Data Collector Verification

**Purpose:** Verifies that the Kafka data collector is working correctly and saving files as expected.

**What it does:**
- Checks that output directory structure exists
- Verifies checkpoint file exists and is valid
- Tests that data files contain valid JSON
- Checks Kafka topic status and partition distribution
- Explains why only some partitions may be used

**Prerequisites:**
- Kafka container must be running
- Data collector should be running (or have run previously)
- Producer should have sent some messages

**How to Run:**

**Option A: Run in Docker (Recommended)**
```bash
docker exec -it kafka python3 /app/src/testers/test_data_collector.py
```

**Option B: Run Locally**
```bash
python3 src/testers/test_data_collector.py
```

**Expected Output:**
```
================================================================================
Kafka Data Collector Test Suite
================================================================================

Output Directory: /app/src/data/kafka_streaming
Checkpoint File: /app/src/data/kafka_streaming/checkpoints/offset_checkpoint.json
Topic: weather-raw
Kafka Broker: kafka:9092

================================================================================
TEST 1: Directory Structure
================================================================================
✓ Output directory exists: /app/src/data/kafka_streaming
✓ Found 1 date directories:
  - 2025-12-13
✓ Checkpoint directory exists: /app/src/data/kafka_streaming/checkpoints

================================================================================
TEST 2: Checkpoint File
================================================================================
✓ Checkpoint file exists
✓ Checkpoint file is valid JSON
  Last updated: 2025-12-13T10:30:00Z
  Offsets for weather-raw:
    Partition 0: 12345
    Partition 1: 12340
    ...

================================================================================
TEST 3: Data Files
================================================================================
✓ Found 5 .jsonl file(s)
  Testing: Madison_2025-12-13.jsonl
    Lines: 100
    ✓ All checked lines are valid JSON
    Sample data keys: ['station_id', 'station_name', 'timestamp', ...]

================================================================================
TEST 4: Kafka Topic Status
================================================================================
✓ Topic weather-raw exists
  Total partitions: 4
  Partition IDs: [0, 1, 2, 3]

================================================================================
TEST 5: Partition Distribution
================================================================================
  Sampling up to 100 messages to check partition distribution...
  ✓ Sampled 100 messages
  Partition distribution:
    Partition 0: 25 messages (25.0%)
    Partition 1: 30 messages (30.0%)
    Partition 2: 45 messages (45.0%)
  Partitions used: 3
  ⚠ Only 3 out of 4 partitions have messages
    → This is normal if:
      - Kafka uses hash(key) % num_partitions for partitioning
      - Station IDs hash to only some partitions
      - Not all partitions have received messages yet

================================================================================
TEST SUMMARY
================================================================================
✓ PASS: Directory Structure
✓ PASS: Checkpoint File
✓ PASS: Data Files
✓ PASS: Kafka Topic Status
✓ PASS: Partition Distribution

Results: 5/5 tests passed
```

**Why Only 3 Partitions Are Used:**

Kafka's default partitioner uses: `hash(key) % num_partitions`

- Your producer uses `station_id` as the message key
- With 5 stations and 4 partitions, the hash values may only map to 3 partitions
- This is **normal behavior** - Kafka distributes based on key hash, not round-robin
- All messages for the same station go to the same partition (maintains order)
- If you want to use all 4 partitions, you could:
  - Use more stations (more keys = better distribution)
  - Use a custom partitioner
  - Use `None` as key (round-robin, but loses per-station ordering)

**To Stop:** The tester runs once and exits (unlike the other testers)

---

## Notes

- Both testers run **continuously** until you stop them with `Ctrl+C`
- They use **consumer groups**, so multiple instances can run in parallel (each will consume different partitions)
- The testers are designed for **development/debugging** purposes
- For production monitoring, consider using Kafka's built-in tools or a proper monitoring solution
- **Partition Distribution**: It's normal for only some partitions to be used if you have fewer unique keys than partitions

