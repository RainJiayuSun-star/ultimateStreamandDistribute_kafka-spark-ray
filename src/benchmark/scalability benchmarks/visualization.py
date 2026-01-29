"""
Visualization generator for scalability benchmark results.

Generates graphs for:
- Horizontal scaling (throughput vs workers)
- Load scaling (latency/lag vs load)
- Partition scaling (throughput/balance vs partitions)
"""

import json
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List
import seaborn as sns

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 11


def plot_horizontal_scaling(results: Dict, output_dir: Path):
    """Generate graphs for horizontal scaling tests."""
    if 'horizontal_scaling' not in results:
        return
    
    data = results['horizontal_scaling']
    tests = data.get('tests', [])
    
    if not tests:
        return
    
    # Extract data
    workers = [t['workers'] for t in tests]
    throughput = [t.get('estimated_throughput_msg_per_sec', 0) for t in tests]
    spark_lag = [t.get('avg_spark_consumer_lag', 0) for t in tests]
    ray_lag = [t.get('avg_ray_consumer_lag', 0) for t in tests]
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Horizontal Scaling Benchmark Results', fontsize=16, fontweight='bold')
    
    # 1. Throughput vs Workers
    ax1 = axes[0, 0]
    ax1.plot(workers, throughput, 'o-', linewidth=2, markersize=8, color='steelblue')
    ax1.set_xlabel('Number of Workers', fontsize=12)
    ax1.set_ylabel('Throughput (msg/sec)', fontsize=12)
    ax1.set_title('Throughput Scaling', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(workers)
    
    # Add linear scaling reference
    if len(throughput) > 0 and throughput[0] > 0:
        linear_ref = [throughput[0] * w / workers[0] for w in workers]
        ax1.plot(workers, linear_ref, '--', alpha=0.5, color='gray', label='Linear Scaling')
        ax1.legend()
    
    # 2. Consumer Lag vs Workers
    ax2 = axes[0, 1]
    x = np.arange(len(workers))
    width = 0.35
    ax2.bar(x - width/2, spark_lag, width, label='Spark Consumer Lag', color='coral', alpha=0.7)
    ax2.bar(x + width/2, ray_lag, width, label='Ray Consumer Lag', color='lightblue', alpha=0.7)
    ax2.set_xlabel('Number of Workers', fontsize=12)
    ax2.set_ylabel('Consumer Lag (messages)', fontsize=12)
    ax2.set_title('Consumer Lag vs Workers', fontsize=13, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(workers)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Scaling Efficiency
    ax3 = axes[1, 0]
    if len(throughput) > 0 and throughput[0] > 0:
        efficiency = []
        for i, w in enumerate(workers):
            expected = throughput[0] * w / workers[0]
            actual = throughput[i]
            eff = (actual / expected * 100) if expected > 0 else 0
            efficiency.append(eff)
        
        ax3.bar(workers, efficiency, color='green', alpha=0.7)
        ax3.axhline(y=100, color='red', linestyle='--', linewidth=2, label='100% (Linear)')
        ax3.set_xlabel('Number of Workers', fontsize=12)
        ax3.set_ylabel('Scaling Efficiency (%)', fontsize=12)
        ax3.set_title('Scaling Efficiency', fontsize=13, fontweight='bold')
        ax3.set_ylim([0, max(120, max(efficiency) * 1.1)])
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Resource Usage (if available)
    ax4 = axes[1, 1]
    cpu_data = []
    mem_data = []
    for t in tests:
        cpu = t.get('cpu_usage', {})
        mem = t.get('memory_usage', {})
        if cpu:
            cpu_data.append(sum(cpu.values()) / len(cpu) if cpu else 0)
        else:
            cpu_data.append(0)
        if mem:
            mem_data.append(sum(mem.values()) / len(mem) if mem else 0)
        else:
            mem_data.append(0)
    
    if cpu_data or mem_data:
        x = np.arange(len(workers))
        width = 0.35
        if any(cpu_data):
            ax4.bar(x - width/2, cpu_data, width, label='CPU Usage (%)', color='orange', alpha=0.7)
        if any(mem_data):
            ax4.bar(x + width/2, mem_data, width, label='Memory Usage (%)', color='purple', alpha=0.7)
        ax4.set_xlabel('Number of Workers', fontsize=12)
        ax4.set_ylabel('Resource Usage (%)', fontsize=12)
        ax4.set_title('Resource Utilization', fontsize=13, fontweight='bold')
        ax4.set_xticks(x)
        ax4.set_xticklabels(workers)
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')
    else:
        ax4.text(0.5, 0.5, 'Resource usage data\nnot available', 
                ha='center', va='center', fontsize=12)
        ax4.set_title('Resource Utilization', fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    output_file = output_dir / 'horizontal_scaling_results.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {output_file}")


def plot_load_scaling(results: Dict, output_dir: Path):
    """Generate graphs for load scaling tests."""
    if 'load_scaling' not in results:
        return
    
    data = results['load_scaling']
    tests = data.get('tests', [])
    
    if not tests:
        return
    
    # Extract data
    rates = [t['target_rate'] for t in tests]
    actual_rates = [t.get('actual_rate', 0) for t in tests]
    spark_lag = [t.get('avg_spark_consumer_lag', 0) for t in tests]
    ray_lag = [t.get('avg_ray_consumer_lag', 0) for t in tests]
    max_spark_lag = [t.get('max_spark_consumer_lag', 0) for t in tests]
    max_ray_lag = [t.get('max_ray_consumer_lag', 0) for t in tests]
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Load Scaling Benchmark Results', fontsize=16, fontweight='bold')
    
    # 1. Actual Rate vs Target Rate
    ax1 = axes[0, 0]
    ax1.plot(rates, rates, '--', linewidth=2, color='gray', label='Target Rate', alpha=0.7)
    ax1.plot(rates, actual_rates, 'o-', linewidth=2, markersize=8, color='steelblue', label='Actual Rate')
    ax1.set_xlabel('Target Rate (msg/sec)', fontsize=12)
    ax1.set_ylabel('Actual Rate (msg/sec)', fontsize=12)
    ax1.set_title('Rate Accuracy', fontsize=13, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Consumer Lag vs Load
    ax2 = axes[0, 1]
    ax2.plot(rates, spark_lag, 'o-', linewidth=2, markersize=8, label='Avg Spark Lag', color='coral')
    ax2.plot(rates, ray_lag, 's-', linewidth=2, markersize=8, label='Avg Ray Lag', color='lightblue')
    ax2.plot(rates, max_spark_lag, '--', linewidth=1, alpha=0.7, label='Max Spark Lag', color='coral')
    ax2.plot(rates, max_ray_lag, '--', linewidth=1, alpha=0.7, label='Max Ray Lag', color='lightblue')
    ax2.set_xlabel('Load (msg/sec)', fontsize=12)
    ax2.set_ylabel('Consumer Lag (messages)', fontsize=12)
    ax2.set_title('Consumer Lag vs Load', fontsize=13, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')  # Log scale for better visualization
    
    # 3. Lag Growth Rate
    ax3 = axes[1, 0]
    if len(spark_lag) > 1:
        spark_growth = np.diff(spark_lag) / np.diff(rates) if np.any(np.diff(rates)) else [0]
        ray_growth = np.diff(ray_lag) / np.diff(rates) if np.any(np.diff(rates)) else [0]
        mid_rates = [(rates[i] + rates[i+1]) / 2 for i in range(len(rates) - 1)]
        
        ax3.plot(mid_rates, spark_growth, 'o-', linewidth=2, markersize=8, label='Spark Lag Growth', color='coral')
        ax3.plot(mid_rates, ray_growth, 's-', linewidth=2, markersize=8, label='Ray Lag Growth', color='lightblue')
        ax3.set_xlabel('Load (msg/sec)', fontsize=12)
        ax3.set_ylabel('Lag Growth Rate (messages per msg/sec)', fontsize=12)
        ax3.set_title('Lag Growth Rate', fontsize=13, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # 4. Error Rate (if available)
    ax4 = axes[1, 1]
    errors = [t.get('errors', 0) for t in tests]
    messages_sent = [t.get('messages_sent', 1) for t in tests]
    error_rates = [(e / m * 100) if m > 0 else 0 for e, m in zip(errors, messages_sent)]
    
    ax4.bar(rates, error_rates, color='red', alpha=0.7, width=min(np.diff(rates)) * 0.8 if len(rates) > 1 else rates[0] * 0.1)
    ax4.set_xlabel('Load (msg/sec)', fontsize=12)
    ax4.set_ylabel('Error Rate (%)', fontsize=12)
    ax4.set_title('Error Rate vs Load', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_file = output_dir / 'load_scaling_results.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {output_file}")


def plot_partition_scaling(results: Dict, output_dir: Path):
    """Generate graphs for partition scaling tests."""
    if 'partition_scaling' not in results:
        return
    
    data = results['partition_scaling']
    tests = data.get('tests', [])
    
    if not tests:
        return
    
    # Extract data
    partitions = [t['partitions'] for t in tests]
    actual_rates = [t.get('actual_rate', 0) for t in tests]
    balance_scores = [t.get('balance_score', 0) for t in tests]
    spark_lag = [t.get('spark_consumer_lag', 0) for t in tests]
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Partition Scaling Benchmark Results', fontsize=16, fontweight='bold')
    
    # 1. Throughput vs Partitions
    ax1 = axes[0, 0]
    ax1.plot(partitions, actual_rates, 'o-', linewidth=2, markersize=8, color='steelblue')
    ax1.set_xlabel('Number of Partitions', fontsize=12)
    ax1.set_ylabel('Throughput (msg/sec)', fontsize=12)
    ax1.set_title('Throughput vs Partitions', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(partitions)
    
    # 2. Partition Balance Score
    ax2 = axes[0, 1]
    ax2.bar(partitions, balance_scores, color='green', alpha=0.7, width=min(np.diff(partitions)) * 0.8 if len(partitions) > 1 else partitions[0] * 0.3)
    ax2.axhline(y=100, color='red', linestyle='--', linewidth=2, label='Perfect Balance (100%)')
    ax2.set_xlabel('Number of Partitions', fontsize=12)
    ax2.set_ylabel('Balance Score (%)', fontsize=12)
    ax2.set_title('Partition Balance', fontsize=13, fontweight='bold')
    ax2.set_ylim([0, 105])
    ax2.set_xticks(partitions)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Consumer Lag vs Partitions
    ax3 = axes[1, 0]
    ax3.bar(partitions, spark_lag, color='coral', alpha=0.7, width=min(np.diff(partitions)) * 0.8 if len(partitions) > 1 else partitions[0] * 0.3)
    ax3.set_xlabel('Number of Partitions', fontsize=12)
    ax3.set_ylabel('Spark Consumer Lag (messages)', fontsize=12)
    ax3.set_title('Consumer Lag vs Partitions', fontsize=13, fontweight='bold')
    ax3.set_xticks(partitions)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Scaling Efficiency
    ax4 = axes[1, 1]
    if len(actual_rates) > 0 and actual_rates[0] > 0:
        efficiency = []
        for i, p in enumerate(partitions):
            expected = actual_rates[0] * p / partitions[0]
            actual = actual_rates[i]
            eff = (actual / expected * 100) if expected > 0 else 0
            efficiency.append(eff)
        
        ax4.bar(partitions, efficiency, color='purple', alpha=0.7, width=min(np.diff(partitions)) * 0.8 if len(partitions) > 1 else partitions[0] * 0.3)
        ax4.axhline(y=100, color='red', linestyle='--', linewidth=2, label='100% (Linear)')
        ax4.set_xlabel('Number of Partitions', fontsize=12)
        ax4.set_ylabel('Scaling Efficiency (%)', fontsize=13, fontweight='bold')
        ax4.set_title('Scaling Efficiency', fontsize=13, fontweight='bold')
        ax4.set_ylim([0, max(120, max(efficiency) * 1.1) if efficiency else 120])
        ax4.set_xticks(partitions)
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_file = output_dir / 'partition_scaling_results.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {output_file}")


def generate_all_visualizations(results: Dict, output_dir: Path):
    """Generate all visualizations for benchmark results."""
    print("\nGenerating visualizations...")
    
    plot_horizontal_scaling(results, output_dir)
    plot_load_scaling(results, output_dir)
    plot_partition_scaling(results, output_dir)
    
    print("Visualization generation complete!")
