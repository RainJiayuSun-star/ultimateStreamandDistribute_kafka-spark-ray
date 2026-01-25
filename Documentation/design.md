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

Commands:
```

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



