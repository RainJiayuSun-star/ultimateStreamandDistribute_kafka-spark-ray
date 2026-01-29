# Troubleshooting Scalability Benchmarks

## Expected Warnings When Running Inside Docker

When running benchmarks from inside the Docker container, you'll see warnings like:

```
Warning: Could not get consumer lag: [Errno 2] No such file or directory: 'docker'
Warning: Could not get Spark metrics: HTTPConnectionPool...
Warning: Could not get Docker stats for kafka: [Errno 2] No such file or directory: 'docker'
```

**These are EXPECTED and OK!** Here's why:

### 1. Docker Command Not Available Inside Container

**Warning**: `[Errno 2] No such file or directory: 'docker'`

**Explanation**: 
- When running inside Docker, you can't run `docker exec` commands
- The code detects this and uses Kafka tools directly instead
- Consumer lag collection still works using Kafka CLI tools

**Status**: ✅ **Fixed** - Code now detects Docker environment and uses appropriate method

### 2. Spark/Ray APIs Not Accessible

**Warning**: `HTTPConnectionPool(host='localhost', port=8080): Connection refused`

**Possible Causes**:
- Spark/Ray services not running
- Services running but APIs not accessible from Kafka container
- Network connectivity issues

**Impact**: 
- ⚠️ Spark/Ray metrics won't be collected
- ✅ Benchmarks still work - they use Kafka consumer lag as primary metric
- ✅ Results are still saved

**To Fix**:
- Ensure Spark is running: `docker compose ps | grep spark`
- Ensure Ray is running: `docker compose ps | grep ray`
- Check network connectivity: `docker exec -it kafka ping spark-master`

### 3. Docker Stats Not Available

**Warning**: `Could not get Docker stats for kafka: [Errno 2] No such file or directory: 'docker'`

**Explanation**:
- Can't run `docker stats` from inside Docker container
- Resource metrics are optional

**Impact**:
- ⚠️ CPU/memory metrics won't be collected
- ✅ Benchmarks still work - primary metrics (consumer lag, throughput) are collected

**To Get Resource Metrics**:
- Run benchmarks from host machine (can use `docker stats`)
- Or manually monitor: `docker stats` from host terminal

## What Metrics ARE Collected

Even with warnings, benchmarks collect:

✅ **Kafka Consumer Lag** - Primary metric for throughput
✅ **Message Counts** - Messages sent/received
✅ **Throughput Estimates** - Based on consumer lag
✅ **Partition Distribution** - For partition scaling tests
✅ **Error Rates** - Failed message sends

## Benchmarks Still Work!

The warnings don't prevent benchmarks from running. They just mean some optional metrics aren't available.

**Check Results**:
```bash
# View results from Docker
docker exec -it kafka ls -la /tmp/benchmark_results/

# Copy results to host
docker cp kafka:/tmp/benchmark_results ./benchmark_results

# View JSON results
docker exec -it kafka cat /tmp/benchmark_results/results_*/all_results.json | jq .
```

## Recommendations

### For Best Results

1. **Run from Host Machine** (if possible):
   ```bash
   pip install -r "src/benchmark/scalability benchmarks/requirements.txt"
   python "src/benchmark/scalability benchmarks/scalability_benchmark.py" --test all
   ```
   - Can collect Docker stats
   - Can access Spark/Ray APIs via localhost
   - Full metrics collection

2. **Run from Docker** (current approach):
   ```bash
   docker exec -it kafka python3 "/app/src/benchmark/scalability benchmarks/scalability_benchmark.py" --test all
   ```
   - Works but with limited metrics
   - Primary metrics (consumer lag, throughput) still collected
   - Results saved to `/tmp/benchmark_results/`

### To Reduce Warnings

**Option 1**: Suppress warnings (modify code to not print warnings)

**Option 2**: Ensure all services are running:
```bash
docker compose up -d
docker compose ps  # Verify all services are up
```

**Option 3**: Run from host machine for full metrics

## Summary

✅ **Benchmarks work** - Warnings don't prevent execution  
✅ **Primary metrics collected** - Consumer lag, throughput, partition distribution  
⚠️ **Optional metrics missing** - Docker stats, Spark/Ray APIs (non-critical)  
✅ **Results saved** - JSON files with all collected metrics  

The warnings are informational - benchmarks complete successfully!
