"""
ML-Based Failure Predictor (Patched Version)
Loads real trained models from models/
"""

import numpy as np
import joblib
import logging
from typing import Dict, List
import os
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class FailurePredictor:
    def __init__(self):

        # REAL model paths (matches your actual trained filenames)
        self.model_path = "/app/models/"

        self.failure_model = None
        self.healing_model = None
        self.scaler = None
        self.feature_names = [
            'build_duration_avg','test_count','changed_files','commit_size',
            'hour_of_day','day_of_week','previous_failures','dependency_changes',
            'code_complexity','test_coverage','author_failure_rate','branch_age_days'
        ]

        self.is_model_loaded = False

    async def load_model(self):
        """Load trained ML models from container /app/models directory"""

        try:
            failure_model_file = os.path.join(self.model_path, "failure_predictor.pkl")
            healing_model_file = os.path.join(self.model_path, "healing_predictor.pkl")
            scaler_file = os.path.join(self.model_path, "scaler.pkl")
            metadata_file = os.path.join(self.model_path, "metadata.pkl")

            if not os.path.exists(failure_model_file):
                logger.error("❌ Failure model not found at /app/models/")
                return False

            self.failure_model = joblib.load(failure_model_file)
            self.scaler = joblib.load(scaler_file)

            # Healing model is optional
            if os.path.exists(healing_model_file):
                self.healing_model = joblib.load(healing_model_file)
            else:
                logger.warning("⚠ No healing model found, using fallback")

            logger.info("✅ ML models loaded successfully")
            self.is_model_loaded = True
            return True

        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
            return False

    def is_loaded(self):
        return self.is_model_loaded

    async def predict_failure(self, workflow_run: Dict) -> Dict:
        """Return ML-based failure probability"""

        if not self.is_model_loaded:
            return {"error": "Model not loaded"}

        try:
            features = self._extract_features(workflow_run)
            scaled = self.scaler.transform([features])
            prob = float(self.failure_model.predict_proba(scaled)[0][1])

            return {
                "will_fail": prob > 0.5,
                "confidence": prob,
                "risk_level": self._risk(prob),
                "factors": self._factors(features)
            }

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"error": str(e)}

    async def predict_healing_success(self, failure_analysis: Dict) -> float:
        """Return probability healing will work"""
        try:
            if self.healing_model is None:
                return 0.5  # fallback

            features = self._healing_features(failure_analysis)
            scaled = self.scaler.transform([features])
            prob = float(self.healing_model.predict_proba(scaled)[0][1])
            return prob

        except Exception as e:
            logger.error(f"Healing prediction error: {e}")
            return 0.5

    # -----------------------------
    # FEATURE EXTRACTION
    # -----------------------------
    def _extract_features(self, run: Dict) -> List[float]:
        created = datetime.fromisoformat(
            run.get("created_at", "2025-01-01T00:00:00").replace("Z", "+00:00")
        )

        return [
            run.get("build_duration_avg", 300),
            run.get("test_count", 50),
            run.get("changed_files", 5),
            run.get("commit_size", 120),
            created.hour,
            created.weekday(),
            run.get("previous_failures", 0),
            run.get("dependency_changes", 0),
            run.get("code_complexity", 10),
            run.get("test_coverage", 80),
            run.get("author_failure_rate", 0.10),
            (datetime.now(timezone.utc) - created).days

        ]

    def _healing_features(self, f: Dict) -> List[float]:
        return [
            1.0 if f.get("fixable") else 0.0,
            len(f.get("stack_trace", "")),
            1.0 if f.get("missing_package") else 0.0,
            {"critical": 1, "high": 0.8, "medium": 0.5}.get(f.get("severity"), 0.3),
            0.8
        ]

    # -----------------------------
    # HELPERS
    # -----------------------------
    def _risk(self, p):
        if p >= 0.8: return "very_high"
        if p >= 0.6: return "high"
        if p >= 0.4: return "medium"
        if p >= 0.2: return "low"
        return "very_low"

    def _factors(self, features):
        output = []
        if features[6] > 2: output.append("High recent failure rate")
        if features[7] > 0: output.append("Dependency changes")
        if features[3] > 300: output.append("Large commit size")
        if features[9] < 70: output.append("Low test coverage")
        return output or ["No major risk factors"]

