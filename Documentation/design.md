# Implementation Design Document

## Overview
This project implements a Lambda Architecture (https://www.geeksforgeeks.org/system-design/what-is-lambda-architecture-system-design/#what-is-lambda-architecture) for real-time weather forecasting. It builds upon course project p7: Kafka, Weather Data. It integrates three distinct distributed system to leverage their respective strengths:
- Kafka: High-throughput data ingestion and decoupling
- Spark: Stateful stream processing and data parallelism (ETL)
- Ray: Low-latency logical parallelism for Machine Learning inference

The System ingests raw weather station data, aggregates it using a sliding window in Spark to reduce noise, and passes the aggregated features to a Ray cluster to detect anomalies and predict future trends in real-time.

## Deployment
Deployment will be done on a single VM via Docker Compose. The cluster will consists of the following 5 primary type of containers:

1. kafka: Single broker, acting as the central nervous system
2. spark-master: coordinator for the ETL pipeline
3. spark-worker: executes the heavy windowing/aggregation tasks.
4. ray-head: manages the ML actors and serves the Ray Dashboard
5. ray-worker: executes the training/inference actors.

### Commands:
To see the Topic Contents
#### Method 1: Use existing tester scripts
View weather-raw topic: 
```
# In Docker
docker exec -it kafka python3 /app/src/testers/debug_consumer.py

# Or locally (if Kafka accessible from host)
python3 src/testers/debug_consumer.py
```
---
View weather-feature topic: 
```
# In Docker
docker exec -it spark-master python3 /app/src/testers/test_spark_features.py

# Or locally
python3 src/testers/test_spark_features.py
```
---
View weather-predictions topic:
```
# In Docker
docker exec -it kafka python3 /app/src/testers/test_ray_predictions.py

# Or locally
python3 src/testers/test_ray_predictions.py
```

#### Method 1: Use Kafka console consumer (raw messages)
View messages from beginning
```
# weather-raw topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw \
  --from-beginning

# weather-features topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-features \
  --from-beginning

# weather-predictions topic
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-predictions \
  --from-beginning
```
View only new messages (latest):
```
# Remove --from-beginning flag
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw
```
View limited number of messages:
```
# View only 5 messages
docker exec -it kafka /kafka_2.12-3.6.2/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic weather-raw \
  --from-beginning \
  --max-messages 5
```

## Communication Mechanisms
- not decided yet

## System Design


## Client Interface


## Evaluation & Performance


## Project Roadmap / Todo



## Data or Dataset
- Method 1: Live API: Open-Meteo free weather api: https://open-meteo.com/
- Method 2: Historical Replay: Historical Hourly Weather Data 2012-2017 from Kaggle: https://www.kaggle.com/datasets/selfishgene/historical-hourly-weather-data



