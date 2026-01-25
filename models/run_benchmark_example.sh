#!/bin/bash
# Example script to run model benchmarking

# Set paths
DATA_PATH="src/data/historical/madison1996_2025_combined_cleaned.csv"
OUTPUT_DIR="models/benchmark_results"

# Benchmark all models
echo "Benchmarking all models..."
python models/benchmark_models.py \
    --data "$DATA_PATH" \
    --output "$OUTPUT_DIR"

echo "Benchmarking complete! Check results in $OUTPUT_DIR"

