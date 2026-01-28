# Fine-Tuning LSTM on Hourly Data

This guide explains how to fine-tune a pre-trained LSTM model (trained on daily data) on hourly patterns.

## Overview

Fine-tuning allows you to:
- ✅ Leverage knowledge learned from daily patterns
- ✅ Adapt to hourly/diurnal cycles
- ✅ Potentially improve accuracy for short-term forecasts
- ✅ Use transfer learning approach

## Prerequisites

1. **Pre-trained model**: A model trained on daily data (e.g., `LSTM_20260124_184927`)
2. **Hourly data**: `src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv`
3. **GPU**: Recommended for faster training (RTX 4070 Mobile)

## Quick Start

### Basic Fine-Tuning

```bash
python src/ray/training/finetune_lstm_hourly.py \
    --pretrained-model models/trained/forecasting/LSTM_20260124_184927 \
    --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv \
    --epochs 30 \
    --learning-rate 0.0001 \
    --use-gpu \
    --mixed-precision
```

### Fine-Tuning with Frozen Layers (Transfer Learning)

```bash
python src/ray/training/finetune_lstm_hourly.py \
    --pretrained-model models/trained/forecasting/LSTM_20260124_184927 \
    --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv \
    --epochs 30 \
    --learning-rate 0.0001 \
    --freeze-layers \
    --use-gpu \
    --mixed-precision
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--pretrained-model` | Required | Path to pre-trained model directory |
| `--hourly-data` | Required | Path to hourly normals CSV |
| `--lookback` | 24 | Number of hours to look back |
| `--forecast-horizon` | 24 | Number of hours to predict ahead |
| `--epochs` | 30 | Number of fine-tuning epochs |
| `--batch-size` | 32 | Batch size for training |
| `--learning-rate` | 0.0001 | Learning rate (lower than initial training) |
| `--freeze-layers` | False | Freeze all layers except last (transfer learning) |
| `--use-gpu` | True | Use GPU acceleration |
| `--mixed-precision` | False | Enable FP16 mixed precision |

## Fine-Tuning Strategies

### 1. **Full Fine-Tuning** (Default)
- All layers are trainable
- Lower learning rate (0.0001 vs 0.001)
- Good when hourly patterns are similar to daily patterns

### 2. **Transfer Learning** (`--freeze-layers`)
- Freezes all layers except the last Dense layer
- Only the output layer learns hourly patterns
- Faster training, less risk of overfitting
- Good when you want to preserve daily knowledge

### 3. **Progressive Unfreezing**
- Start with frozen layers
- Gradually unfreeze layers during training
- Most sophisticated approach
- (Not implemented in current script, but can be added)

## How It Works

1. **Load Pre-trained Model**: Loads the daily-trained LSTM model
2. **Feature Mapping**: Maps hourly features to match daily features:
   - `temperature` → `temperature` (direct)
   - `wind_avg` → `wind_speed` (proxy)
   - `precipitation` → Not available in hourly normals
3. **Adapt Architecture**: Checks if input shape matches, adapts if needed
4. **Create New Scalers**: Hourly data has different distribution, needs new scalers
5. **Fine-tune**: Continues training with lower learning rate
6. **Save**: Saves fine-tuned model with metadata

## Expected Results

Fine-tuning on hourly data should help the model:
- ✅ Learn diurnal temperature patterns (day/night cycles)
- ✅ Capture hourly wind variations
- ✅ Understand short-term weather dynamics
- ✅ Improve 1-24 hour ahead forecasts

## Feature Compatibility

**Daily Model Features:**
- `temperature`
- `wind_avg`
- `precipitation`

**Hourly Data Features:**
- `temperature` ✅ (matches)
- `wind_speed` ✅ (proxy for wind_avg)
- `dewpoint` (additional)
- `wind_direction` (additional)
- `humidity` (approximated)
- `precipitation` ❌ (not in hourly normals)

The script automatically maps compatible features.

## Example Workflow

```bash
# Step 1: Train on daily data (if not already done)
python src/ray/training/train_lstm.py \
    --daily-data src/data/historical/madison1996_2025_combined_cleaned.csv \
    --epochs 50 \
    --use-gpu \
    --mixed-precision

# Step 2: Fine-tune on hourly data
python src/ray/training/finetune_lstm_hourly.py \
    --pretrained-model models/trained/forecasting/LSTM_20260124_184927 \
    --hourly-data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv \
    --epochs 30 \
    --learning-rate 0.0001 \
    --use-gpu \
    --mixed-precision

# Step 3: Benchmark the fine-tuned model
python models/benchmark_models.py \
    --data src/data/historical_hourly/Madison_Dane_County_2012_hourly.csv \
    --model models/trained/forecasting/LSTM_FineTuned_YYYYMMDD_HHMMSS \
    --output models/benchmark_results
```

## Tips

1. **Learning Rate**: Use 10x lower than initial training (0.0001 vs 0.001)
2. **Epochs**: Fewer epochs needed (20-30 vs 50+)
3. **Early Stopping**: Built-in to prevent overfitting
4. **Freeze Layers**: Use `--freeze-layers` if you want to preserve daily knowledge
5. **Monitor Validation**: Watch for overfitting on hourly data

## Troubleshooting

### Error: "Feature count mismatch"
- **Cause**: Model expects different number of features
- **Solution**: The script automatically adapts, but if it fails, you may need to train from scratch on hourly data

### Error: "Input shape mismatch"
- **Cause**: Lookback window differs (daily uses 7, hourly uses 24)
- **Solution**: Script automatically adjusts, or specify `--lookback 7` to match daily model

### Poor Performance After Fine-Tuning
- **Cause**: Hourly patterns too different from daily
- **Solution**: Try training from scratch on hourly data instead

## Output

The fine-tuned model is saved to:
```
models/trained/forecasting/LSTM_FineTuned_YYYYMMDD_HHMMSS/
├── model.h5              # Fine-tuned model
├── scaler_X.pkl         # New scaler for hourly data
├── scaler_y.pkl         # New scaler for hourly targets
├── feature_adapter.pkl  # Feature adapter
└── metadata.json        # Training metadata (includes pretrained model info)
```

## Comparison: Fine-Tuned vs From Scratch

| Approach | Pros | Cons |
|----------|------|------|
| **Fine-Tuning** | Faster training, leverages daily knowledge, transfer learning | May not adapt well if patterns differ |
| **From Scratch** | Learns hourly patterns directly, no constraints | Longer training, doesn't use daily knowledge |

## Next Steps

After fine-tuning:
1. Benchmark the fine-tuned model
2. Compare with original daily model
3. Compare with model trained from scratch on hourly data
4. Choose the best model for your use case

