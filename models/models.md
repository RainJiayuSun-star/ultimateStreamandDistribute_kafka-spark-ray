# Different Models and Techniques in Weather Forecasting

## Dataset
- ERA5 (a training dataset) has "hourly data on single levels from 1940 to present". It is the most widely used dataset in the weather forecasting research. (https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download) (https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5)
- HRES (High-Resolution Operational Forecasts) dataset  

## Techniques
### Linear Regression
### Deep Learning related

#### Some Desired Models Comparision
| Model | Complexity | Features | Ray/Kafka Difficulty |
|---|---|---|---|
| DeepAR | Medium | Proabilistic (gives a confidence range) | Easy (Ray native)
| StormCast | High | Mesoscale (local city-level detail) | Hard (heavy GPU reqs) | 
| SFNO | High | Methematical Elegance (Fourier Transforms) | Medium (uses NVIDIA Modules)
| XGBoost | Low | Extreme Speed / Anomaly Detection | Very Easy (XGBoost-on-Ray)

## Models chosen
- Pangu-Weather (via ONNX)
- Temporal Fusion Transformer (TFT)
- XGBoost-on-Ray
- GraphCast

## Muli-model Ensamble
### Option 1
Input Validation & Model Robustness.
| Model | Role | Feature | Cost |
|---|---|---|---|
| Pangu-Weather (via ONNX) | Long-term Global Forecasting | Very efficient because it uses a hierarchical architecture (predicting in 1h, 3h, 6h, and 24h intervals). This minimizes the "error accumulation" we might get with models that only on 1-hour steps | Heavyweight, High GPU (~3-4GB VRAM)
| Temporal Fusion Transformer (TFT) | Localized, Multivariate Forecasting | While Pangu sees the "big picture," a TFT is better at looking at specific Kafka stream data. It uses Variable Selection Networks to figure out which features (like humidity vs. pressure) actually matter for the next 5 minutes. | Medium GPU (~1GB VRAM) and high System RAM.
| XGBoost-on-Ray | Real-time Anomaly Detection | Deep learning models are sometimes "too smart"—they try to make sense of bad data. If a weather sensor glitches and sends a temperature of 500°C, XGBoost will catch it instantly (low latency) before it ruins your deep learning inference. This completes the Lambda Architecture. It acts as a "speed layer" filter that protects "batch layer" models | CPU-only (minimal RAM). |



## References
- DeepAR Forecasting Algorithm (https://www.geeksforgeeks.org/deep-learning/deepar-forecasting-algorithm/)
- Machine Learning Methods for Weather Forecasting: A Survey (https://www.mdpi.com/2073-4433/16/1/82)