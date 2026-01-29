"""
Metrics collector for scalability benchmarks.

Collects metrics from:
- Kafka: Consumer lag, throughput, partition distribution
- Spark: Processing throughput (via Kafka consumer lag)
- Ray: Inference throughput (via Kafka consumer lag)
- System: CPU, memory usage via Docker stats
"""

import json
import time
import subprocess
import requests
from typing import Dict, List, Optional
from collections import defaultdict
from kafka import KafkaConsumer, KafkaAdminClient
import os


class MetricsCollector:
    """Collects metrics from various system components."""
    
    def __init__(self, broker: str = 'localhost:9092'):
        self.broker = broker
        self.admin_client = None
        self._init_admin_client()
    
    def _init_admin_client(self):
        """Initialize Kafka admin client."""
        try:
            self.admin_client = KafkaAdminClient(bootstrap_servers=[self.broker])
        except Exception as e:
            print(f"Warning: Could not initialize Kafka admin client: {e}")
    
    def get_kafka_consumer_lag(self, topic: str, consumer_group: str) -> Dict[int, int]:
        """
        Get consumer lag for a topic and consumer group.
        
        Returns:
            Dictionary mapping partition -> lag (messages)
        """
        lag_by_partition = {}
        
        try:
            # Use kafka-consumer-groups.sh via subprocess
            cmd = [
                'docker', 'exec', 'kafka',
                '/kafka_2.12-3.6.2/bin/kafka-consumer-groups.sh',
                '--bootstrap-server', 'localhost:9092',
                '--group', consumer_group,
                '--describe'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if topic in line and 'LAG' in line:
                        parts = line.split()
                        if len(parts) >= 6:
                            try:
                                partition = int(parts[1])
                                lag = int(parts[5])
                                lag_by_partition[partition] = lag
                            except (ValueError, IndexError):
                                pass
        except Exception:
            # This is OK - consumer lag metrics are optional
            # Silently return empty dict
            pass
        
        return lag_by_partition
    
    def get_kafka_topic_offsets(self, topic: str) -> Dict[int, int]:
        """
        Get latest offsets for all partitions of a topic.
        
        Returns:
            Dictionary mapping partition -> latest offset
        """
        offsets = {}
        
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=[self.broker],
                consumer_timeout_ms=1000
            )
            
            partitions = consumer.partitions_for_topic(topic)
            if partitions:
                for partition in partitions:
                    tp = consumer.assignment()
                    if tp:
                        # Get end offsets
                        end_offsets = consumer.end_offsets([(topic, partition)])
                        offsets[partition] = end_offsets.get((topic, partition), 0)
            
            consumer.close()
        except Exception as e:
            print(f"Warning: Could not get topic offsets: {e}")
        
        return offsets
    
    def get_kafka_throughput(self, topic: str, duration: float = 5.0) -> float:
        """
        Measure Kafka throughput by counting messages over a duration.
        
        Returns:
            Messages per second
        """
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[self.broker],
                auto_offset_reset='latest',
                consumer_timeout_ms=int(duration * 1000),
                enable_auto_commit=False
            )
            
            start_time = time.time()
            message_count = 0
            
            for message in consumer:
                message_count += 1
                if time.time() - start_time >= duration:
                    break
            
            consumer.close()
            
            elapsed = time.time() - start_time
            return message_count / elapsed if elapsed > 0 else 0.0
            
        except Exception as e:
            print(f"Warning: Could not measure Kafka throughput: {e}")
            return 0.0
    
    def get_spark_metrics(self) -> Dict:
        """
        Get Spark metrics from Spark UI.
        
        Returns:
            Dictionary with Spark metrics
        """
        metrics = {
            'batch_processing_time': None,
            'scheduling_delay': None,
            'processing_delay': None,
            'throughput': None
        }
        
        try:
            # Check if running inside Docker
            is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
            spark_host = 'spark-master' if is_inside_docker else 'localhost'
            
            # Try to get metrics from Spark UI REST API
            spark_ui_url = f'http://{spark_host}:8080/api/v1/applications'
            response = requests.get(spark_ui_url, timeout=2)
            
            if response.status_code == 200:
                apps = response.json()
                if apps:
                    app_id = apps[0]['id']
                    # Get streaming metrics
                    streaming_url = f'http://{spark_host}:8080/api/v1/applications/{app_id}/streaming/statistics'
                    streaming_response = requests.get(streaming_url, timeout=2)
                    
                    if streaming_response.status_code == 200:
                        stats = streaming_response.json()
                        if stats:
                            # Extract metrics
                            metrics['batch_processing_time'] = stats.get('avgInputRate', 0)
                            metrics['throughput'] = stats.get('avgInputRate', 0)
        except Exception:
            # This is OK - Spark metrics are optional
            pass
        
        return metrics
    
    def get_ray_metrics(self) -> Dict:
        """
        Get Ray metrics from Ray Dashboard API.
        
        Returns:
            Dictionary with Ray metrics
        """
        metrics = {
            'num_actors': 0,
            'inference_throughput': None,
            'actor_memory': {}
        }
        
        try:
            # Check if running inside Docker
            is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
            ray_host = 'ray-head' if is_inside_docker else 'localhost'
            
            # Try to get metrics from Ray Dashboard API
            ray_api_url = f'http://{ray_host}:8265/api/actors'
            response = requests.get(ray_api_url, timeout=2)
            
            if response.status_code == 200:
                actors = response.json().get('data', {}).get('actors', {})
                metrics['num_actors'] = len(actors)
                
                # Get memory usage per actor
                for actor_id, actor_info in actors.items():
                    memory = actor_info.get('memory', {})
                    metrics['actor_memory'][actor_id] = memory
        except Exception:
            # This is OK - Ray metrics are optional
            pass
        
        return metrics
    
    def get_docker_stats(self, container_name: str) -> Dict:
        """
        Get Docker container stats (CPU, memory).
        
        Returns:
            Dictionary with CPU and memory usage
        """
        stats = {
            'cpu_percent': 0.0,
            'memory_usage_mb': 0.0,
            'memory_limit_mb': 0.0,
            'memory_percent': 0.0
        }
        
        # Check if running inside Docker - can't use docker stats from inside container
        is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
        if is_inside_docker:
            # Docker stats not available from inside container - return empty stats silently
            return stats
        
        try:
            cmd = ['docker', 'stats', '--no-stream', '--format', 'json', container_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                if data:
                    # Parse CPU percentage
                    cpu_str = data.get('CPUPerc', '0%').rstrip('%')
                    stats['cpu_percent'] = float(cpu_str) if cpu_str else 0.0
                    
                    # Parse memory
                    mem_str = data.get('MemUsage', '0B / 0B')
                    mem_parts = mem_str.split(' / ')
                    if len(mem_parts) == 2:
                        # Convert to MB
                        usage_str = mem_parts[0]
                        limit_str = mem_parts[1]
                        
                        stats['memory_usage_mb'] = self._parse_size(usage_str)
                        stats['memory_limit_mb'] = self._parse_size(limit_str)
                        
                        if stats['memory_limit_mb'] > 0:
                            stats['memory_percent'] = (stats['memory_usage_mb'] / stats['memory_limit_mb']) * 100
        except Exception:
            # Docker stats are optional - fail silently
            pass
        
        return stats
    
    def _parse_size(self, size_str: str) -> float:
        """Parse size string (e.g., '1.5GiB') to MB."""
        size_str = size_str.strip().upper()
        
        multipliers = {
            'B': 1 / (1024 * 1024),
            'KB': 1 / 1024,
            'MB': 1,
            'GB': 1024,
            'GIB': 1024,
            'MIB': 1.048576
        }
        
        for unit, multiplier in multipliers.items():
            if size_str.endswith(unit):
                try:
                    value = float(size_str[:-len(unit)])
                    return value * multiplier
                except ValueError:
                    pass
        
        return 0.0
    
    def collect_all_metrics(self, duration: float = 10.0) -> Dict:
        """
        Collect all metrics over a duration.
        
        Returns:
            Dictionary with all collected metrics
        """
        metrics = {
            'timestamp': time.time(),
            'kafka': {},
            'spark': {},
            'ray': {},
            'system': {}
        }
        
        # Collect Kafka metrics
        spark_lag = self.get_kafka_consumer_lag('weather-raw', 'spark-streaming')
        ray_lag = self.get_kafka_consumer_lag('weather-features', 'ray-ml-inference')
        
        metrics['kafka'] = {
            'spark_consumer_lag': sum(spark_lag.values()) if spark_lag else 0,
            'ray_consumer_lag': sum(ray_lag.values()) if ray_lag else 0,
            'spark_lag_by_partition': spark_lag,
            'ray_lag_by_partition': ray_lag
        }
        
        # Collect Spark metrics
        metrics['spark'] = self.get_spark_metrics()
        
        # Collect Ray metrics
        metrics['ray'] = self.get_ray_metrics()
        
        # Collect system metrics
        containers = ['kafka', 'spark-master', 'spark-worker1', 'ray-head', 'ray-worker1']
        for container in containers:
            stats = self.get_docker_stats(container)
            metrics['system'][container] = stats
        
        return metrics
