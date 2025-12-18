# Kafka Data Collector

This script collects real-time weather data from the `weather-raw` Kafka topic and saves it to files for training purposes. It includes fault tolerance features to ensure no data loss.

## Purpose

- **Collect Training Data**: Save real-time Kafka stream data to files
- **Fault Tolerance**: Checkpointing ensures no data loss on crashes
- **Organized Storage**: Files organized by date and station
- **Exactly-Once Semantics**: Each message saved exactly once

## Features

### Fault Tolerance

1. **Manual Offset Management**
   - Offsets only committed after successful file writes
   - Prevents data loss if crash occurs during write

2. **Checkpointing**
   - Saves last committed offsets to file
   - Recovers from checkpoint on restart
   - Resumes from last saved position

3. **Atomic File Writes**
   - Writes to `.tmp` file first
   - Renames to final file after successful write
   - Prevents partial/corrupted files

4. **Batch Processing**
   - Accumulates messages in batches (100 messages or 5 minutes)
   - Reduces I/O operations
   - More efficient than writing each message individually

## File Structure

```
src/data/kafka_streaming/
├── 2025-12-13/
│   ├── Madison_2025-12-13.jsonl
│   ├── Chicago_2025-12-13.jsonl
│   └── ...
├── 2025-12-14/
│   └── ...
└── checkpoints/
    └── offset_checkpoint.json
```

### File Format

Files use **JSON Lines** format (`.jsonl`):
- One JSON object per line
- Easy to process line-by-line
- Can be read with `pandas.read_json(file, lines=True)`

Example:
```json
{"station_id": "KMSN", "station_name": "Madison", "timestamp": "2025-12-13T10:30:00Z", "temperature": 45.2, ...}
{"station_id": "KMSN", "station_name": "Madison", "timestamp": "2025-12-13T10:35:00Z", "temperature": 45.5, ...}
```

## Usage

### Run in Docker (Recommended)

```bash
# Start the data collector in background
docker exec -d kafka python3 /app/src/kafka_weather/data_collector.py

# Or run in foreground to see logs
docker exec -it kafka python3 /app/src/kafka_weather/data_collector.py
```

### Run Locally

```bash
# From project root
python3 src/kafka_weather/data_collector.py
```

### Check if Running

```bash
# Check if process is running
docker exec kafka ps aux | grep data_collector

# Check logs
docker logs kafka | grep -i "data.collector\|checkpoint"
```

### Stop Gracefully

Press `Ctrl+C` - the collector will:
1. Process remaining batch
2. Save final checkpoint
3. Close consumer cleanly

## Configuration

### Environment Variables

Set these before running (or edit the script):

```bash
# Output directory
export DATA_COLLECTOR_OUTPUT_DIR="src/data/kafka_streaming"

# Batch size (messages per batch)
export DATA_COLLECTOR_BATCH_SIZE="100"

# Batch timeout (seconds)
export DATA_COLLECTOR_BATCH_TIMEOUT="300"  # 5 minutes

# Offset reset strategy
export DATA_COLLECTOR_OFFSET_RESET="earliest"  # or "latest"
```

### Default Settings

- **Batch Size**: 100 messages
- **Batch Timeout**: 5 minutes (300 seconds)
- **Checkpoint Interval**: 60 seconds
- **Offset Reset**: `earliest` (captures all data)

## How It Works

### Normal Operation

1. **Consume Messages**: Reads from `weather-raw` topic
2. **Buffer Messages**: Accumulates in memory batch
3. **Write Batch**: When batch is full or timeout reached:
   - Groups messages by station and date
   - Writes to appropriate files (atomic)
   - Saves checkpoint with offsets
4. **Repeat**: Continues consuming

### Crash Recovery

1. **On Restart**: Loads checkpoint file
2. **Seek to Position**: Seeks to last committed offset
3. **Resume**: Continues from where it left off
4. **No Duplicates**: Messages already saved are skipped

### Checkpoint File

Location: `src/data/kafka_streaming/checkpoints/offset_checkpoint.json`

Format:
```json
{
  "last_updated": "2025-12-13T10:30:00Z",
  "offsets": {
    "weather-raw": {
      "0": 12345,
      "1": 12340,
      "2": 12350,
      "3": 12335
    }
  }
}
```

## Integration with Training Pipeline

### Using Collected Data

The collected data can be used in your Ray training pipeline:

```python
# In src/ray/training/data_loader.py
import pandas as pd
from pathlib import Path

def load_kafka_streaming_data(data_dir: Path):
    """Load collected Kafka streaming data."""
    all_data = []
    
    for date_dir in data_dir.glob("*/"):
        for jsonl_file in date_dir.glob("*.jsonl"):
            df = pd.read_json(jsonl_file, lines=True)
            all_data.append(df)
    
    return pd.concat(all_data, ignore_index=True)
```

### Combining with Historical Data

1. **Daily Historical Data**: From `getHistoricaldata.py` (TMAX, TMIN, etc.)
2. **Kafka Streaming Data**: Real-time hourly data (actual temperature, humidity, etc.)
3. **Combine**: Use both in training for richer features

## Monitoring

### Check Data Collection

```bash
# Count messages collected today
find src/data/kafka_streaming/$(date +%Y-%m-%d) -name "*.jsonl" -exec wc -l {} + | tail -1

# Check file sizes
ls -lh src/data/kafka_streaming/$(date +%Y-%m-%d)/

# View recent data
tail -20 src/data/kafka_streaming/$(date +%Y-%m-%d)/Madison_*.jsonl
```

### Check Checkpoint Status

```bash
# View checkpoint
cat src/data/kafka_streaming/checkpoints/offset_checkpoint.json

# Check last update time
stat src/data/kafka_streaming/checkpoints/offset_checkpoint.json
```

### Check Kafka Consumer Lag

```bash
# Check consumer group lag
docker exec kafka /kafka_2.12-3.6.2/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group kafka-data-collector \
  --describe
```

## Troubleshooting

### No Data Being Saved

1. **Check if producer is running**:
   ```bash
   docker logs kafka | grep producer
   ```

2. **Check if consumer is connected**:
   ```bash
   docker exec kafka ps aux | grep data_collector
   ```

3. **Check Kafka topic has messages**:
   ```bash
   docker exec kafka /kafka_2.12-3.6.2/bin/kafka-run-class.sh \
     kafka.tools.GetOffsetShell \
     --broker-list localhost:9092 \
     --topic weather-raw
   ```

4. **Check offset reset strategy**:
   - If using `latest`, it only gets NEW messages after collector starts
   - Use `earliest` to get all historical messages

### Checkpoint Not Updating

- Check write permissions on checkpoint directory
- Check disk space
- Check logs for errors

### Duplicate Messages

- Check if multiple collectors are running (same consumer group)
- Only one collector should run per consumer group

### Missing Messages

- Check if collector crashed and didn't recover
- Check checkpoint file for last saved offsets
- Restart collector - it should resume from checkpoint

## Best Practices

1. **Run Continuously**: Keep collector running in background
2. **Monitor Disk Space**: Streaming data can accumulate quickly
3. **Regular Cleanup**: Archive old data periodically
4. **Backup Checkpoints**: Checkpoint file is critical for recovery
5. **Single Instance**: Only run one collector per consumer group

## Next Steps

After collecting data:

1. **Verify Data Quality**: Check collected files
2. **Create Daily Aggregator**: Aggregate hourly data into daily summaries
3. **Use in Training**: Load collected data in Ray training pipeline
4. **Combine Sources**: Merge with historical daily data for comprehensive training set

## Example: Daily Aggregator

You can create a script to aggregate collected Kafka data into daily summaries:

```python
# src/kafka_weather/daily_aggregator.py
# Aggregates hourly Kafka data into daily summaries
# Similar to historical daily data format
```

This would allow you to:
- Use real-time Kafka data for hourly forecasting
- Use aggregated daily summaries for daily forecasting
- Combine both for comprehensive training

