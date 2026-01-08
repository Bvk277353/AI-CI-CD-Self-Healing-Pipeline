# pipeline-monitor/app/metrics.py
from prometheus_client import Counter, Gauge

# Pipeline run / outcome
PIPELINE_RUNS = Counter(
    "pipeline_runs_total",
    "Total pipeline runs observed"
)

PIPELINE_SUCCESS = Counter(
    "pipeline_success_total",
    "Total successful pipeline runs"
)

# Prediction confidence (set last seen)
PIPELINE_PRED_CONF = Gauge(
    "pipeline_prediction_confidence_avg",
    "Last prediction confidence (0..1)"
)

# Healing actions
PIPELINE_HEAL_ACTIONS = Counter(
    "pipeline_healing_actions_total",
    "Number of healing actions executed"
)
