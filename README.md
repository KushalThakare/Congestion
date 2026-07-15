# Network Congestion Detection

A machine learning pipeline that detects network congestion using the **NSL-KDD** dataset (or a realistic synthetic fallback).

---

## Project Structure

```
project/
├── data/                   # Auto-downloaded NSL-KDD files land here
├── models/                 # Saved trained model (.pkl)
├── results/                # Evaluation plots (confusion matrix, ROC, feature importance)
├── src/
│   ├── generate_data.py    # NSL-KDD downloader + realistic synthetic generator
│   ├── train_model.py      # Training pipeline with cross-validation + model saving
│   └── evaluate.py         # Full metrics, plots, feature importance
├── main.py                 # Orchestrates everything
└── requirements.txt
```

---

## Quickstart

```bash
pip install -r requirements.txt

# Run with NSL-KDD (downloads automatically)
python main.py

# Run with synthetic data (no download needed)
python main.py --synthetic

# Use Gradient Boosting instead of Random Forest
python main.py --model gb
```

---

## Dataset — NSL-KDD

NSL-KDD is a cleaned version of the classic KDD Cup 1999 dataset.

- **Label mapping:** DoS (Denial of Service) attacks → `congestion = 1`, Normal traffic → `congestion = 0`
- DoS attack types included: `neptune, smurf, pod, teardrop, land, back, apache2, udpstorm, processtable, mailbomb`
- Files downloaded from: https://github.com/defcom17/NSL_KDD

---

## Outputs

| File | Description |
|------|-------------|
| `results/confusion_matrix.png` | TP/TN/FP/FN breakdown |
| `results/roc_curve.png`        | ROC curve with AUC score |
| `results/feature_importance.png` | Top features by importance |
| `models/random_forest_congestion.pkl` | Saved model (loadable with joblib) |

---

## Why NSL-KDD over the original synthetic data?

The original synthetic version labeled congestion using a hardcoded rule on only 2 of 4 features, meaning the model was reverse-engineering your own `if` statement. NSL-KDD provides real network traffic captures with meaningful, multi-dimensional signal — the model has to actually learn.
