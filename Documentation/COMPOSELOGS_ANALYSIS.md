# composelogs.txt Analysis

**Log period:** 2026-01-27, ~23:34:48 onward  
**Source:** `docker compose up` output (merged logs from all services)

---

## Executive Summary

| Component | Status | Notes |
|-----------|--------|-------|
| **Ray head** | ✅ Running | Ray runtime started; /dev/shm warning |
| **Ray workers (1–4)** | ✅ Running | All connected to head |
| **Kafka** | ✅ Running | KRaft mode; topics created |
| **Kafka producer** | ✅ Running | Publishing to `weather-raw` every 15s |
| **Spark master** | ✅ Running | Master up |
| **Spark workers (1–4)** | ✅ Running | Registered; WeatherStreamingApp executors launched |
| **Spark streaming** | ✅ Running | Query started successfully |
| **Kafka data collector** | ✅ Running | Saving batches; checkpoint updates |
| **Ray inference** | ❌ **Failing** | Connection errors; restart loop |
| **API** | ⚠️ Not clearly visible | No explicit API errors in sampled logs |

---

## 1. Ray head & workers

**Ray head (23:34:45–23:34:50):**
- Local node IP: `172.18.0.3`
- Ray runtime started
- GCS/dashboard: `172.18.0.3:8265`
- Connect: `ray start --address='172.18.0.3:6379'`

**Warnings:**
- Object store using `/tmp` instead of `/dev/shm` (64 MB). Suggestion: `--shm-size=0.51gb` (or more) for Docker.
- Brief “Some processes … have not registered with GCS” during startup; normal.

**Ray workers:**
- ray-worker1–4: “Ray runtime started,” connected to head.
- Same /dev/shm warning (suggestion: `--shm-size=2.05gb` for workers).

---

## 2. Kafka

**Startup (~23:34:48–23:34:51):**
- KRaft, single node
- Controller → Leader
- Raft + metadata loader OK

**Producer:**
- Fetches NWS for 5 stations (KMSN, KMKE, KMDW, KMSP, KDSM) every 15s
- Publishes to `weather-raw`; iterations 9–57+ observed (5/5 messages each)
- No producer errors in logs

**Consumer groups observed:**
- `kafka-data-collector`: saving raw data
- `spark-streaming-group`: Spark consumes `weather-raw`
- `spark-features-test`: tester for `weather-features` (joined then left)
- `debug`: debug consumer (one member removed on heartbeat expiration)
- `ray-predictions-test-group`: tester for `weather-predictions`
- `ray-inference-test-group`: `test_ray_inference.py` (joined ~23:39:14)

---

## 3. Spark

**Master:** Ready; workers register.

**Streaming (23:35:45–23:35:46):**
- Application: `WeatherStreamingApp`
- App ID: `app-20260127233546-0000`
- Executors on workers 1–4
- “Streaming query started successfully!”

**Warnings:**
- “topic was processed” / empty micro-batches (multiple); typically harmless when no new data in a trigger.

---

## 4. Kafka data collector

- Consumes `weather-raw`, writes JSONL, updates checkpoint.
- Batches: 18–23 messages each; checkpoint updates ~every 1 min.
- Offsets progress (e.g. partition 1: 9 → 17 → 25 → … → 65).

**Earlier:** `NotCoordinatorForGroupError` for `kafka-data-collector` around 23:35:06 during Kafka startup; group coordinator not ready yet. Transient.

---

## 5. Ray inference — failing

**Observed behavior:** Ray-inference container restarts repeatedly and **never** connects to the Ray cluster.

**Error (repeated):**
```text
ValueError: Can't find a `node_ip_address.json` file from
/tmp/ray/session_2026-01-27_23-34-45_963846_7. for 60 seconds.
A ray instance hasn't started. Did you do `ray start` or `ray.init` on this host?
```

**Sequence each restart:**
1. TensorFlow loads (CPU, no CUDA).
2. “Checking connectivity to Ray head at ray-head:6379” → **reachable**.
3. “Ray dashboard is accessible at ray-head:8265, GCS should be ready”.
4. Waits 20s, then “Attempting Ray connection (attempt 1/3)”.
5. Either:
   - “Ray connection attempt timed out after 30s,” retry 2/3, 3/3, or
   - “Ray connection failed: Can't find a `node_ip_address.json` file…”
6. After 3 attempts → exit; container restarts (e.g. 23:37:59, 23:41:14, 23:44:28, 23:47:42, 23:50:57).

**Cause:**  
`ray.init(address=...)` in the **ray-inference** container is trying to use a **local** Ray session (looks for `node_ip_address.json` under `/tmp/ray/session_*` **inside** the ray-inference container). The ray-inference container does not run `ray start`; it should act only as a **client** to the ray-head. The reference to `session_2026-01-27_23-34-45_963846_7` matches the **ray-head** session (started 23:34:45), but the client is incorrectly looking for it locally.

**Impact:**
- No inference runs in production.
- `weather-features` is not consumed by ray-inference.
- `weather-predictions` is not produced.
- API has no predictions to serve.

**Fix (already applied in code):**  
Clear local Ray session dirs and avoid starting a local node (see `INFERENCE_FIXES.md`). Ensure the **ray-inference** container uses the updated `ray_consumer.py` and that the fix is deployed (image rebuild / compose up).

---

## 6. API

- No explicit API startup or error lines in the composelogs excerpts.
- Likely running (API container in compose), but without ray-inference no predictions are written to `weather-predictions`, so endpoints that serve predictions would return empty or 404.

---

## 7. Warnings and non-fatal issues

| Issue | Component | Severity |
|-------|-----------|----------|
| Object store using /tmp | Ray head, workers | Medium – performance |
| /dev/shm too small | Ray | Medium – add `--shm-size` in Docker |
| NotCoordinatorForGroupError | kafka-data-collector | Low – startup only |
| Debug consumer “failed” / removed | Kafka group `debug` | Low – consumer quit or timeout |
| “topic was processed” (empty batches) | Spark streaming | Low – normal when no data |
| SIGTERM handler not main thread | ray-inference | Low – Ray worker warning |
| TensorFlow: no CUDA, no TensorRT | ray-inference | Low – CPU-only setup |

---

## 8. Data flow from logs

```text
NWS API → Kafka producer → weather-raw ✅
         → Kafka data collector (raw → JSONL) ✅

weather-raw → Spark streaming (WeatherStreamingApp) ✅
            → weather-features ( Spark → Kafka ) ✅

weather-features → Ray inference ❌ (container never connects)
                 → weather-predictions ❌ (not produced)

weather-predictions → API ❌ (no data)
```

---

## 9. Recommendations

1. **Ray-inference**
   - Deploy the updated `ray_consumer.py` (session cleanup + client-only connection).
   - Rebuild the ray-inference image and restart the stack.
   - Confirm “Connected to Ray cluster” in `docker logs ray-inference`.

2. **Ray /dev/shm**
   - Add `shm_size` (e.g. `0.51gb` for head, `2gb` for workers) in `docker-compose` for Ray services to use `/dev/shm` for object store.

3. **Monitoring**
   - After fix, check `weather-predictions` has new messages (e.g. console consumer or Kafdrop).
   - Hit API prediction endpoints and verify non-empty responses.

4. **Composelogs**
   - These logs are from **before** the ray-inference connection fix. Re-run `docker compose up` with the fixed code and capture new logs to verify ray-inference connects and the full pipeline runs.

---

## 10. Log / service timeline (simplified)

| Time (approx) | Event |
|---------------|--------|
| 23:34:45–50 | Ray head starts; Kafka controller up; Spark workers register |
| 23:35:45–46 | Spark submits WeatherStreamingApp; executors launched |
| 23:35:47 | Ray-inference first start; TF load; connectivity checks OK |
| 23:36:06 | Kafka data collector first “Batch processed successfully” |
| 23:36:09–37:59 | Ray-inference connection attempts → failure → exit |
| 23:37:28 | Kafka producer iteration 10 (5/5 published) |
| 23:38:11–40 | Spark-features-test consumer joins then leaves; debug consumer removed |
| 23:39:01–50:57 | Ray-inference restarts and fails repeatedly (same error) |
| 23:39:03–17 | Ray-predictions-test-group, ray-inference-test-group join (manual testers) |
| 23:49–50 | Kafka producer iterations 54–57; data collector checkpoints continue |

---

**Summary:**  
Infrastructure (Kafka, Spark, Ray cluster, producer, data collector, streaming) is up and processing. The **ray-inference** container is the only critical failure: it never connects to Ray, so the ML step and prediction publishing are missing. Deploying and verifying the ray-inference connection fix should restore the end-to-end pipeline.
