"""
Partition scaling benchmarks.

Tests performance with different Kafka partition counts.
Uses the existing benchmark_partition_scaling.py script.
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from metrics_collector import MetricsCollector


def run_partition_scaling_tests(
    partitions_list: List[int],
    stations: int = 50,
    rate: float = 50.0,
    duration: int = 300,
    broker: str = None,
    results_dir: Path = None
) -> Dict:
    """
    Run partition scaling tests using the benchmark_partition_scaling.py script.
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
        'test_type': 'partition_scaling',
        'partitions_tested': partitions_list,
        'stations': stations,
        'rate': rate,
        'duration_per_test': duration,
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    script_path = Path(__file__).parent.parent.parent / 'scripts' / 'benchmark_partition_scaling.py'
    
    for partitions in partitions_list:
        print(f"\n{'=' * 80}")
        print(f"Testing with {partitions} partition(s)")
        print(f"{'=' * 80}")
        
        # Collect baseline metrics
        print("Collecting baseline metrics...")
        baseline_metrics = collector.collect_all_metrics(duration=5.0)
        
        # Run benchmark script
        print(f"Running partition benchmark...")
        cmd = [
            sys.executable,
            str(script_path),
            '--partitions', str(partitions),
            '--stations', str(stations),
            '--rate', str(rate),
            '--duration', str(duration),
            '--broker', broker
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 60)
        
        # Parse output
        output = result.stdout
        test_result = {
            'partitions': partitions,
            'success': result.returncode == 0,
            'output': output
        }
        
        # Extract metrics from output
        for line in output.split('\n'):
            if 'Messages Sent:' in line:
                try:
                    test_result['messages_sent'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Actual Rate:' in line:
                try:
                    test_result['actual_rate'] = float(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif 'Partition Balance Score:' in line:
                try:
                    test_result['balance_score'] = float(line.split(':')[1].strip().split('%')[0])
                except:
                    pass
        
        # Collect metrics after test
        print("Collecting post-test metrics...")
        post_metrics = collector.collect_all_metrics(duration=5.0)
        test_result['spark_consumer_lag'] = post_metrics['kafka'].get('spark_consumer_lag', 0)
        test_result['ray_consumer_lag'] = post_metrics['kafka'].get('ray_consumer_lag', 0)
        
        results['tests'].append(test_result)
        
        print(f"\nResults for {partitions} partition(s):")
        print(f"  Messages Sent: {test_result.get('messages_sent', 0)}")
        print(f"  Actual Rate: {test_result.get('actual_rate', 0):.2f} msg/sec")
        print(f"  Balance Score: {test_result.get('balance_score', 0):.2f}%")
        print(f"  Spark Consumer Lag: {test_result.get('spark_consumer_lag', 0):.0f} messages")
        
        # Wait between tests
        if partitions != partitions_list[-1]:
            print("\nWaiting 10 seconds before next test...")
            import time
            time.sleep(10)
    
    # Save results
    results_file = results_dir / 'partition_scaling_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    return results
