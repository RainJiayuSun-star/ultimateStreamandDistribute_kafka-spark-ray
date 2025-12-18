#!/bin/bash
# Script to start Spark Structured Streaming application
# This should be run after Spark master and workers are up

set -e

echo "=========================================="
echo "Starting Spark Structured Streaming"
echo "=========================================="

# Wait for Spark master to be ready
echo "Waiting for Spark master to be ready..."
max_retries=60
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if nc -z spark-master 7077 2>/dev/null; then
        echo "Spark master is ready!"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "Waiting for Spark master... ($retry_count/$max_retries)"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "ERROR: Spark master did not become ready after $max_retries attempts"
    exit 1
fi

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if nc -z kafka 9092 2>/dev/null; then
        echo "Kafka is ready!"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "Waiting for Kafka... ($retry_count/$max_retries)"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "ERROR: Kafka did not become ready after $max_retries attempts"
    exit 1
fi

# Additional wait to ensure everything is fully initialized
echo "Waiting additional 5 seconds for full initialization..."
sleep 5

# Start Spark streaming application
echo "=========================================="
echo "Submitting Spark streaming job..."
echo "=========================================="

cd /app

spark-submit \
    --master spark://spark-master:7077 \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.7 \
    --conf "spark.sql.streaming.checkpointLocation=/app/checkpoints/spark" \
    --conf "spark.sql.streaming.stopGracefullyOnShutdown=true" \
    --driver-memory 1g \
    --executor-memory 1g \
    /app/src/spark/streaming_app.py 2>&1 | tee /app/checkpoints/spark-streaming.log

echo "Spark streaming application started!"

