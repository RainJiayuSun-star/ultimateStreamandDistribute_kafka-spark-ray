#!/usr/bin/env python3
"""
Main scalability benchmark runner.

This script orchestrates scalability benchmarks for:
- Horizontal scaling (Spark/Ray workers)
- Load scaling (different message rates)
- Partition scaling

Usage:
    python scalability_benchmark.py --test horizontal --workers 1,2,4,8
    python scalability_benchmark.py --test load --rates 1,10,50,100
    python scalability_benchmark.py --test partition --partitions 2,4,8
    python scalability_benchmark.py --test all
"""

import argparse
import json
import time
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from metrics_collector import MetricsCollector
from horizontal_scaling import run_horizontal_scaling_tests
from load_scaling import run_load_scaling_tests
from partition_scaling import run_partition_scaling_tests
from visualization import generate_all_visualizations


def main():
    parser = argparse.ArgumentParser(
        description='Run scalability benchmarks for Kafka-Spark-Ray pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test horizontal scaling with 1, 2, 4, 8 workers
  python scalability_benchmark.py --test horizontal --workers 1,2,4,8 --duration 300
  
  # Test load scaling with different message rates
  python scalability_benchmark.py --test load --rates 1,10,50,100 --duration 300
  
  # Test partition scaling
  python scalability_benchmark.py --test partition --partitions 2,4,8 --duration 300
  
  # Run all tests
  python scalability_benchmark.py --test all --duration 300
        """
    )
    
    parser.add_argument(
        '--test', '-t',
        type=str,
        choices=['horizontal', 'load', 'partition', 'all'],
        default='all',
        help='Type of test to run (default: all)'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=str,
        default='1,2,4',
        help='Comma-separated list of worker counts for horizontal scaling (default: 1,2,4)'
    )
    
    parser.add_argument(
        '--rates', '-r',
        type=str,
        default='1,10,50',
        help='Comma-separated list of message rates (msg/sec) for load scaling (default: 1,10,50)'
    )
    
    parser.add_argument(
        '--partitions', '-p',
        type=str,
        default='2,4,8',
        help='Comma-separated list of partition counts for partition scaling (default: 2,4,8)'
    )
    
    parser.add_argument(
        '--duration', '-d',
        type=int,
        default=300,
        help='Duration per test in seconds (default: 300)'
    )
    
    parser.add_argument(
        '--stations', '-s',
        type=int,
        default=50,
        help='Number of synthetic stations for load/partition tests (default: 50)'
    )
    
    parser.add_argument(
        '--broker', '-b',
        type=str,
        default=None,
        help='Kafka broker address (default: localhost:9092 or KAFKA_BROKER env var)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output directory (default: benchmark/scalability benchmarks/output)'
    )
    
    parser.add_argument(
        '--no-viz',
        action='store_true',
        help='Skip visualization generation'
    )
    
    args = parser.parse_args()
    
    # Set up output directory
    # Check if running inside Docker and if src is read-only
    is_inside_docker = os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME', '').startswith('kafka')
    
    if args.output:
        output_dir = Path(args.output)
    else:
        # If inside Docker and src is read-only, use /tmp (always writable)
        if is_inside_docker:
            # Use /tmp which is always writable in Docker containers
            output_dir = Path('/tmp') / 'benchmark_results'
        else:
            # Running from host - use relative to script
            output_dir = Path(__file__).parent / 'output'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped results directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_dir = output_dir / f'results_{timestamp}'
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("Scalability Benchmark Suite")
    print("=" * 80)
    print(f"Test Type: {args.test}")
    print(f"Duration per test: {args.duration} seconds")
    print(f"Output directory: {results_dir}")
    print("=" * 80)
    
    all_results = {}
    
    # Run tests based on type
    if args.test in ['horizontal', 'all']:
        print("\n" + "=" * 80)
        print("Running Horizontal Scaling Tests")
        print("=" * 80)
        workers_list = [int(w.strip()) for w in args.workers.split(',')]
        results = run_horizontal_scaling_tests(
            workers_list=workers_list,
            duration=args.duration,
            broker=args.broker,
            results_dir=results_dir
        )
        all_results['horizontal_scaling'] = results
    
    if args.test in ['load', 'all']:
        print("\n" + "=" * 80)
        print("Running Load Scaling Tests")
        print("=" * 80)
        rates_list = [float(r.strip()) for r in args.rates.split(',')]
        results = run_load_scaling_tests(
            rates_list=rates_list,
            stations=args.stations,
            duration=args.duration,
            broker=args.broker,
            results_dir=results_dir
        )
        all_results['load_scaling'] = results
    
    if args.test in ['partition', 'all']:
        print("\n" + "=" * 80)
        print("Running Partition Scaling Tests")
        print("=" * 80)
        partitions_list = [int(p.strip()) for p in args.partitions.split(',')]
        results = run_partition_scaling_tests(
            partitions_list=partitions_list,
            stations=args.stations,
            rate=max([float(r.strip()) for r in args.rates.split(',')]),
            duration=args.duration,
            broker=args.broker,
            results_dir=results_dir
        )
        all_results['partition_scaling'] = results
    
    # Save all results
    results_file = results_dir / 'all_results.json'
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'=' * 80}")
    print("Benchmark Results Summary")
    print(f"{'=' * 80}")
    print(f"Results saved to: {results_file}")
    
    # Generate visualizations
    if not args.no_viz:
        print("\n" + "=" * 80)
        print("Generating Visualizations")
        print("=" * 80)
        generate_all_visualizations(all_results, results_dir)
        print(f"Visualizations saved to: {results_dir}")
    
    print(f"\n{'=' * 80}")
    print("Benchmark Suite Complete!")
    print(f"{'=' * 80}\n")


if __name__ == '__main__':
    main()
