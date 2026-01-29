#!/bin/bash
# Helper script to run scalability benchmarks from host machine

set -e

echo "=========================================="
echo "Scalability Benchmark Setup"
echo "=========================================="

# Check if Docker Compose is running
if ! docker compose ps | grep -q "kafka"; then
    echo "ERROR: Docker Compose is not running!"
    echo "Please run: docker compose up -d"
    exit 1
fi

echo "✓ Docker Compose is running"

# Check if Python dependencies are installed
echo ""
echo "Checking Python dependencies..."
python3 -c "import kafka" 2>/dev/null || {
    echo "Installing Python dependencies..."
    pip install -r "$(dirname "$0")/requirements.txt"
}

echo "✓ Python dependencies installed"

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCHMARK_SCRIPT="$SCRIPT_DIR/scalability_benchmark.py"

# Run the benchmark with all arguments passed through
echo ""
echo "Running scalability benchmarks..."
echo "=========================================="
python3 "$BENCHMARK_SCRIPT" "$@"
