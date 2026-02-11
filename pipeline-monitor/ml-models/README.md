# ML Models Directory

This directory contains the machine learning models for failure prediction and healing success prediction.

## Files

- `train_predictor.py` - Model training script
- `failure_patterns.py` - Pattern analysis module
- `requirements.txt` - Python dependencies
- `models/` - Directory where trained models are saved

## Model Files (Generated after training)

After running `train_predictor.py`, the following files will be created in the `models/` directory:

- `failure_model.pkl` - Random Forest model for failure prediction
- `healing_model.pkl` - Gradient Boosting model for healing success prediction
- `scaler.pkl` - StandardScaler for feature normalization
- `metadata.pkl` - Model metadata (training date, feature names, version)
- `training_report.txt` - Training performance report
- `feature_importance.png` - Feature importance visualization

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Train models:
```bash
python train_predictor.py
```

3. Verify models were created:
```bash
ls -la models/
```

You should see:
```
models/
├── failure_model.pkl
├── healing_model.pkl
├── scaler.pkl
├── metadata.pkl
├── training_report.txt
└── feature_importance.png
```

## Using the Models

```python
import joblib

# Load models
failure_model = joblib.load('models/failure_model.pkl')
healing_model = joblib.load('models/healing_model.pkl')
scaler = joblib.load('models/scaler.pkl')

# Make predictions
features = [...]  # Your feature vector
features_scaled = scaler.transform([features])
failure_prob = failure_model.predict_proba(features_scaled)[0][1]

print(f"Failure probability: {failure_prob:.2%}")
```

## Model Performance

Expected performance metrics:
- **Failure Prediction Model:**
  - Accuracy: ~86%
  - Precision: ~85%
  - Recall: ~88%
  - F1-Score: ~86%

- **Healing Success Model:**
  - Accuracy: ~80-85%
  - F1-Score: ~80%

## Features Used

The models use 12 features:
1. build_duration_avg - Average build duration
2. test_count - Number of tests
3. changed_files - Files changed in commit
4. commit_size - Lines of code changed
5. hour_of_day - Time of day (0-23)
6. day_of_week - Day of week (0-6)
7. previous_failures - Recent failure count
8. dependency_changes - Dependency file changes
9. code_complexity - Code complexity score
10. test_coverage - Test coverage percentage
11. author_failure_rate - Author's failure rate
12. branch_age_days - Branch age in days

## Retraining

Models should be retrained periodically with real production data:

```bash
# Retrain with new data
python train_predictor.py

# Models will be automatically updated in models/ directory
```

## Testing Pattern Analysis

```bash
python failure_patterns.py
```

This will run a demo showing how different failure types are detected and categorized.

## Notes

- Models are initially trained on synthetic data
- In production, retrain with real pipeline failure data
- Monitor model performance and retrain when accuracy drops below 80%
- Keep at least 1000 samples of historical data for effective training