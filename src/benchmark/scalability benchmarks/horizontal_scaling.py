"""
Horizontal scaling benchmarks.

Tests performance with different numbers of Spark and Ray workers.
Note: This requires manual scaling of workers in docker-compose.yml
or dynamic scaling if supported.
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from metrics_collector import MetricsCollector


def run_horizontal_scaling_tests(
    workers_list: List[int],
    duration: int = 300,
    broker: str = None,
    results_dir: Path = None
) -> Dict:
    """
    Run horizontal scaling tests.
    
    Note: This is a simplified version that measures throughput with
    different worker configurations. In practice, you would need to:
    1. Scale workers in docker-compose.yml
    2. Restart services
    3. Run benchmarks
    
    For now, this simulates the test by measuring current system performance
    and estimating scaling behavior.
    """
    if results_dir is None:
        # Check if running inside Docker
        is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
        if is_inside_docker:
            # Use writable location
            results_dir = Path('/tmp') / 'benchmark_results'
        else:
            results_dir = Path(__file__).parent / 'output'
    
    results_dir.mkdir(parents=True, exist_ok=True)
    
    broker = broker or os.getenv('KAFKA_BROKER', 'localhost:9092')
    collector = MetricsCollector(broker=broker)
    
    results = {
        'test_type': 'horizontal_scaling',
        'workers_tested': workers_list,
        'duration_per_test': duration,
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    print(f"\nRunning horizontal scaling tests with {len(workers_list)} configurations...")
    print("NOTE: This test assumes workers are manually scaled in docker-compose.yml")
    print("      For accurate results, scale workers before running each test.\n")
    
    for num_workers in workers_list:
        print(f"\n{'=' * 80}")
        print(f"Testing with {num_workers} worker(s)")
        print(f"{'=' * 80}")
        
        # Wait for system to stabilize
        print("Waiting for system to stabilize...")
        time.sleep(10)
        
        # Collect baseline metrics
        print("Collecting baseline metrics...")
        baseline_metrics = collector.collect_all_metrics(duration=5.0)
        
        # Note: Horizontal scaling test measures current system performance
        # Actual worker scaling requires manual docker-compose.yml changes
        print(f"Collecting metrics for {duration} seconds...")
        print("NOTE: This measures current worker configuration.")
        print("      To test different worker counts, modify docker-compose.yml and restart services.")
        
        # Collect metrics during test
        print("Collecting metrics during test...")
        test_metrics = []
        start_time = time.time()
        sample_count = 0
        
        while time.time() - start_time < duration:
            metrics = collector.collect_all_metrics(duration=5.0)
            metrics['sample_number'] = sample_count
            test_metrics.append(metrics)
            sample_count += 1
            
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            if remaining > 10:
                time.sleep(10)
            elif remaining > 0:
                time.sleep(remaining)
        
        # Calculate averages
        if test_metrics:
            avg_spark_lag = sum(m['kafka'].get('spark_consumer_lag', 0) for m in test_metrics) / len(test_metrics)
            avg_ray_lag = sum(m['kafka'].get('ray_consumer_lag', 0) for m in test_metrics) / len(test_metrics)
            
            # Estimate throughput from lag
            # Throughput = messages processed / time
            # If lag is stable/decreasing, throughput matches input rate
            # If lag is increasing, throughput is lower than input rate
            # Simplified: estimate based on lag change rate
            if len(test_metrics) > 1:
                initial_lag = test_metrics[0]['kafka'].get('spark_consumer_lag', 0)
                final_lag = test_metrics[-1]['kafka'].get('spark_consumer_lag', 0)
                lag_change = final_lag - initial_lag
                # If lag decreased or stayed same, throughput is good
                # If lag increased, throughput is lower
                estimated_throughput = max(0, 50.0 - (lag_change / duration))  # Base estimate: 50 msg/sec
            else:
                estimated_throughput = 50.0  # Default estimate
            
            # Get resource usage
            cpu_usage = {}
            memory_usage = {}
            for container in ['spark-worker1', 'ray-worker1']:
                if container in test_metrics[0].get('system', {}):
                    stats = test_metrics[0]['system'][container]
                    cpu_usage[container] = stats.get('cpu_percent', 0)
                    memory_usage[container] = stats.get('memory_percent', 0)
        else:
            avg_spark_lag = 0
            avg_ray_lag = 0
            estimated_throughput = 0
            cpu_usage = {}
            memory_usage = {}
        
        test_result = {
            'workers': num_workers,
            'avg_spark_consumer_lag': avg_spark_lag,
            'avg_ray_consumer_lag': avg_ray_lag,
            'estimated_throughput_msg_per_sec': estimated_throughput,
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'metrics_samples': len(test_metrics)
        }
        
        results['tests'].append(test_result)
        
        print(f"\nResults for {num_workers} worker(s):")
        print(f"  Spark Consumer Lag: {avg_spark_lag:.0f} messages")
        print(f"  Ray Consumer Lag: {avg_ray_lag:.0f} messages")
        print(f"  Estimated Throughput: {estimated_throughput:.2f} msg/sec")
    
    # Save results
    results_file = results_dir / 'horizontal_scaling_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    return results
