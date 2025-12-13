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

## Notes

- Both testers run **continuously** until you stop them with `Ctrl+C`
- They use **consumer groups**, so multiple instances can run in parallel (each will consume different partitions)
- The testers are designed for **development/debugging** purposes
- For production monitoring, consider using Kafka's built-in tools or a proper monitoring solution

