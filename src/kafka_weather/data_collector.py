"""
Kafka Data Collector with Fault Tolerance

Consumes messages from weather-raw topic and saves them to files for training data.
Features:
- Manual offset management with checkpointing
- Atomic file writes (no partial files)
- Batch processing for efficiency
- Crash recovery from checkpoints
- Organized by date and station
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from kafka.structs import TopicPartition

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.kafka_config import (
        KAFKA_BOOTSTRAP_SERVERS,
        TOPIC_WEATHER_RAW,
        CONSUMER_GROUP_DATA_COLLECTOR
    )
except ImportError:
    # Fallback for local testing
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    TOPIC_WEATHER_RAW = "weather-raw"
    CONSUMER_GROUP_DATA_COLLECTOR = "kafka-data-collector"

# Configuration
# Use absolute path in container: /app/data/kafka_streaming (writable, not in read-only /app/src)
# Default to /app/data/kafka_streaming for Docker, fallback to src/data/kafka_streaming for local
OUTPUT_DIR = Path(os.getenv("DATA_COLLECTOR_OUTPUT_DIR", "/app/data/kafka_streaming"))
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
CHECKPOINT_FILE = CHECKPOINT_DIR / "offset_checkpoint.json"

# Batch settings
BATCH_SIZE = int(os.getenv("DATA_COLLECTOR_BATCH_SIZE", "100"))  # Messages per batch
BATCH_TIMEOUT_SECONDS = int(os.getenv("DATA_COLLECTOR_BATCH_TIMEOUT", "300"))  # 5 minutes

# Consumer settings
AUTO_OFFSET_RESET = os.getenv("DATA_COLLECTOR_OFFSET_RESET", "earliest")  # 'earliest' or 'latest'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KafkaDataCollector:
    """
    Kafka consumer that saves messages to files with fault tolerance.
    """
    
    def __init__(self):
        self.consumer: Optional[KafkaConsumer] = None
        self.batch_buffer: List[Dict] = []
        self.batch_start_time = time.time()
        self.last_checkpoint_time = time.time()
        self.checkpoint_interval = 60  # Save checkpoint every 60 seconds
        
        # Create output directories
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Data Collector initialized")
        logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")
        logger.info(f"Checkpoint file: {CHECKPOINT_FILE.absolute()}")
    
    def initialize_consumer(self) -> bool:
        """
        Initialize Kafka consumer with manual offset management.
        Returns True if successful, False otherwise.
        """
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    TOPIC_WEATHER_RAW,
                    bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                    group_id=CONSUMER_GROUP_DATA_COLLECTOR,
                    auto_offset_reset=AUTO_OFFSET_RESET,
                    enable_auto_commit=False,  # Manual offset management
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    key_deserializer=lambda k: k.decode('utf-8') if k else None,
                    max_poll_records=BATCH_SIZE,  # Poll up to batch size
                    session_timeout_ms=30000,
                    heartbeat_interval_ms=10000
                )
                
                logger.info(f"Kafka consumer initialized successfully")
                logger.info(f"Consumer group: {CONSUMER_GROUP_DATA_COLLECTOR}")
                logger.info(f"Topic: {TOPIC_WEATHER_RAW}")
                logger.info(f"Auto offset reset: {AUTO_OFFSET_RESET}")
                
                # Load checkpoint and seek to last position
                self.recover_from_checkpoint()
                
                return True
                
            except NoBrokersAvailable:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Kafka broker not available, retrying ({retry_count}/{max_retries})...")
                    time.sleep(2)
                else:
                    logger.error("Failed to connect to Kafka after all retries")
                    return False
            except Exception as e:
                logger.error(f"Error initializing Kafka consumer: {e}")
                return False
        
        return False
    
    def load_checkpoint(self) -> Dict:
        """
        Load checkpoint file with last committed offsets.
        Returns dictionary with offsets per partition.
        """
        if not CHECKPOINT_FILE.exists():
            logger.info("No checkpoint file found - starting from beginning")
            return {}
        
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"Loaded checkpoint from {CHECKPOINT_FILE}")
            logger.info(f"Last updated: {checkpoint.get('last_updated', 'N/A')}")
            return checkpoint
        except Exception as e:
            logger.warning(f"Error loading checkpoint: {e}. Starting from beginning.")
            return {}
    
    def save_checkpoint(self, offsets: Dict[str, Dict[int, int]]):
        """
        Save checkpoint with current offsets.
        offsets format: {"weather-raw": {0: 12345, 1: 12340, ...}}
        
        Note: Using direct write (not atomic) for better Windows/WSL Docker volume sync.
        Checkpoint loss is not catastrophic - collector will just start from beginning.
        """
        checkpoint = {
            "last_updated": datetime.utcnow().isoformat() + 'Z',
            "offsets": offsets
        }
        
        try:
            # Direct write (better sync on Windows/WSL Docker volumes)
            # For checkpoint files, atomicity is less critical than data files
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint, f, indent=2)
                f.flush()  # Ensure data is written to disk buffer
                os.fsync(f.fileno())  # Force sync to filesystem
            
            # Touch the file to ensure Windows recognizes the change
            try:
                os.utime(CHECKPOINT_FILE, None)
            except OSError:
                pass
            
            logger.info(f"Checkpoint saved: offsets updated to {offsets}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def recover_from_checkpoint(self):
        """
        Recover from checkpoint by seeking to last committed offsets.
        Validates offsets are within range before seeking.
        """
        checkpoint = self.load_checkpoint()
        
        if not checkpoint or not self.consumer:
            logger.info("No checkpoint to recover from - will start from configured offset")
            return
        
        offsets = checkpoint.get('offsets', {})
        topic_offsets = offsets.get(TOPIC_WEATHER_RAW, {})
        
        if not topic_offsets:
            logger.info("No offsets in checkpoint - will start from configured offset")
            return
        
        # Wait for partition assignment
        logger.info("Waiting for partition assignment...")
        self.consumer.poll(timeout_ms=5000)
        
        # Get beginning and end offsets for all partitions to validate checkpoint offsets
        assigned_partitions = list(self.consumer.assignment())
        if not assigned_partitions:
            logger.warning("No partitions assigned yet - cannot recover from checkpoint")
            return
        
        try:
            beginning_offsets = self.consumer.beginning_offsets(assigned_partitions)
            end_offsets = self.consumer.end_offsets(assigned_partitions)
        except Exception as e:
            logger.warning(f"Could not get partition offsets: {e}. Starting from configured offset.")
            return
        
        # Seek to checkpointed offsets, but validate they're within range
        seek_positions = []
        for partition_id_str, checkpoint_offset in topic_offsets.items():
            partition_id = int(partition_id_str)
            partition = TopicPartition(TOPIC_WEATHER_RAW, partition_id)
            
            if partition not in assigned_partitions:
                logger.warning(f"Partition {partition_id} not assigned - skipping")
                continue
            
            # Get valid offset range for this partition
            begin_offset = beginning_offsets.get(partition, 0)
            end_offset = end_offsets.get(partition, 0)
            
            # Validate checkpoint offset is within range
            if checkpoint_offset < begin_offset:
                logger.warning(
                    f"Checkpoint offset {checkpoint_offset} for partition {partition_id} "
                    f"is before beginning ({begin_offset}). Using beginning offset."
                )
                checkpoint_offset = begin_offset
            elif checkpoint_offset > end_offset:
                logger.warning(
                    f"Checkpoint offset {checkpoint_offset} for partition {partition_id} "
                    f"is beyond end ({end_offset}). Using beginning offset to catch up."
                )
                checkpoint_offset = begin_offset
            
            seek_positions.append((partition, checkpoint_offset))
        
        if seek_positions:
            for partition, offset in seek_positions:
                self.consumer.seek(partition, offset)
                logger.info(f"Seeking partition {partition.partition} to offset {offset}")
            logger.info(f"Recovered from checkpoint - resuming from saved positions")
    
    def get_file_path(self, station_name: str, date: datetime) -> Path:
        """
        Get file path for a station and date.
        Format: /app/data/kafka_streaming/YYYY-MM-DD/StationName_YYYY-MM-DD.jsonl (in Docker)
                 or src/data/kafka_streaming/YYYY-MM-DD/StationName_YYYY-MM-DD.jsonl (local)
        """
        date_str = date.strftime('%Y-%m-%d')
        date_dir = OUTPUT_DIR / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize station name for filename
        safe_station_name = station_name.replace(' ', '_').replace('/', '_')
        filename = f"{safe_station_name}_{date_str}.jsonl"
        
        return date_dir / filename
    
    def write_batch_atomic(self, messages: List[Dict]) -> bool:
        """
        Write a batch of messages to files atomically.
        Returns True if successful, False otherwise.
        """
        if not messages:
            return True
        
        # Group messages by station and date
        files_to_write: Dict[Path, List[str]] = {}
        
        for msg_data in messages:
            try:
                station_name = msg_data.get('station_name', 'Unknown')
                timestamp_str = msg_data.get('timestamp', '')
                
                # Parse timestamp to get date
                if 'T' in timestamp_str:
                    date_str = timestamp_str.split('T')[0]
                    msg_date = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    # Fallback to current date
                    msg_date = datetime.utcnow()
                
                file_path = self.get_file_path(station_name, msg_date)
                
                # Prepare JSON line (one JSON object per line)
                json_line = json.dumps(msg_data, ensure_ascii=False) + '\n'
                
                if file_path not in files_to_write:
                    files_to_write[file_path] = []
                files_to_write[file_path].append(json_line)
                
            except Exception as e:
                logger.error(f"Error processing message for file write: {e}")
                continue
        
        # Write all files atomically
        success = True
        for file_path, lines in files_to_write.items():
            try:
                # Atomic write: write to .tmp file, then rename
                temp_file = file_path.with_suffix('.jsonl.tmp')
                
                # Read existing content if file exists (for appending)
                existing_lines = []
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            existing_lines = f.readlines()
                    except Exception as e:
                        logger.warning(f"Could not read existing file {file_path}: {e}")
                
                # Write all content (existing + new) to temp file
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.writelines(existing_lines)  # Write existing content first
                    f.writelines(lines)  # Then append new lines
                
                # Atomic rename (replaces original file)
                temp_file.replace(file_path)
                total_lines = len(existing_lines) + len(lines)
                logger.debug(f"Wrote {len(lines)} new messages to {file_path.name} (total: {total_lines} lines)")
                
            except Exception as e:
                logger.error(f"Error writing to {file_path}: {e}")
                success = False
                if temp_file.exists():
                    temp_file.unlink()
        
        return success
    
    def get_current_offsets(self) -> Dict[str, Dict[int, int]]:
        """
        Get current consumer offsets for all assigned partitions.
        Returns format: {"weather-raw": {0: 12345, 1: 12340, ...}}
        """
        if not self.consumer:
            return {}
        
        offsets = {}
        topic_offsets = {}
        
        for partition in self.consumer.assignment():
            if partition.topic == TOPIC_WEATHER_RAW:
                position = self.consumer.position(partition)
                topic_offsets[str(partition.partition)] = position
        
        if topic_offsets:
            offsets[TOPIC_WEATHER_RAW] = topic_offsets
        
        return offsets
    
    def commit_offsets_after_write(self, success: bool):
        """
        Commit offsets only if write was successful.
        """
        if not self.consumer or not success:
            return
        
        try:
            # Get current positions (these are the offsets we've processed)
            offsets = self.get_current_offsets()
            
            # Save checkpoint
            self.save_checkpoint(offsets)
            
            # Commit to Kafka (optional - checkpoint is primary)
            # self.consumer.commit()
            
            logger.debug(f"Committed offsets: {offsets}")
        except Exception as e:
            logger.error(f"Error committing offsets: {e}")
    
    def should_flush_batch(self) -> bool:
        """
        Check if batch should be flushed (size or timeout).
        """
        size_ready = len(self.batch_buffer) >= BATCH_SIZE
        time_ready = (time.time() - self.batch_start_time) >= BATCH_TIMEOUT_SECONDS
        
        return size_ready or time_ready
    
    def process_batch(self):
        """
        Process current batch: write to files and commit offsets.
        """
        if not self.batch_buffer:
            return
        
        logger.info(f"Processing batch: {len(self.batch_buffer)} messages")
        
        # Write batch to files
        success = self.write_batch_atomic(self.batch_buffer)
        
        if success:
            # Commit offsets only after successful write
            self.commit_offsets_after_write(True)
            logger.info(f"Batch processed successfully: {len(self.batch_buffer)} messages saved")
            self.batch_buffer.clear()
            self.batch_start_time = time.time()
        else:
            logger.error("Batch write failed - will retry in next batch")
            # Don't clear buffer - will retry
    
    def run(self):
        """
        Main loop: consume messages, batch them, and save to files.
        """
        if not self.initialize_consumer():
            logger.error("Failed to initialize consumer. Exiting.")
            return
        
        logger.info("=" * 80)
        logger.info("Kafka Data Collector Started")
        logger.info("=" * 80)
        logger.info(f"Topic: {TOPIC_WEATHER_RAW}")
        logger.info(f"Batch size: {BATCH_SIZE} messages")
        logger.info(f"Batch timeout: {BATCH_TIMEOUT_SECONDS} seconds")
        logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")
        logger.info("=" * 80)
        logger.info("Starting to consume messages...")
        logger.info("Press Ctrl+C to stop gracefully")
        logger.info("=" * 80)
        
        try:
            for message in self.consumer:
                try:
                    # Add message to batch
                    msg_data = message.value
                    self.batch_buffer.append(msg_data)
                    
                    # Check if batch should be flushed
                    if self.should_flush_batch():
                        self.process_batch()
                    
                    # Periodic checkpoint save (even if batch not full)
                    if (time.time() - self.last_checkpoint_time) >= self.checkpoint_interval:
                        if self.batch_buffer:
                            self.process_batch()
                        self.last_checkpoint_time = time.time()
                
                except json.JSONDecodeError as e:
                    logger.error(f"Error deserializing message: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
        
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt signal. Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        finally:
            # Process remaining batch
            if self.batch_buffer:
                logger.info(f"Processing final batch: {len(self.batch_buffer)} messages")
                self.process_batch()
            
            # Close consumer
            if self.consumer:
                self.consumer.close()
                logger.info("Consumer closed")
            
            logger.info("Data Collector stopped")


def main():
    """Main entry point."""
    collector = KafkaDataCollector()
    collector.run()


if __name__ == "__main__":
    main()

