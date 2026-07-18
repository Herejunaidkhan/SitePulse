"""ML severity layer (§5, step 2): blended with — never replacing — the rules-based
score, to keep every alert explainable.

There is no real historical incident_log large enough to train on yet, so this
trains a small logistic-regression model on a synthetic proxy dataset built from
the same domain weights as the rules engine (detection type, zone risk, OSHA
severity). It exists to prove out the blending architecture; swap in a model
trained on real `incident_log` outcomes once enough data accumulates.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

DETECTION_TYPES = ["ppe_violation", "proximity", "fall_risk_posture", "unguarded_edge"]
ZONE_CATEGORIES = ["low", "medium", "high", "critical"]

_ZONE_ORDINAL = {"low": 0.0, "medium": 1.0, "high": 2.0, "critical": 3.0}


def _features(detection_type: str, zone_category: str, confidence: float, repeat_count: int) -> list[float]:
    one_hot = [1.0 if detection_type == t else 0.0 for t in DETECTION_TYPES]
    return [*one_hot, _ZONE_ORDINAL.get(zone_category, 1.0), confidence, float(min(repeat_count, 5))]


def _synthetic_training_set() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed=7)
    base_injury_weight = {"ppe_violation": 0.15, "proximity": 0.35, "fall_risk_posture": 0.55, "unguarded_edge": 0.45}
    rows: list[list[float]] = []
    labels: list[int] = []
    for detection_type in DETECTION_TYPES:
        for zone_category in ZONE_CATEGORIES:
            for confidence in np.linspace(0.5, 0.99, 6):
                for repeat_count in range(0, 4):
                    p = (
                        base_injury_weight[detection_type]
                        + 0.12 * _ZONE_ORDINAL[zone_category]
                        + 0.35 * confidence
                        + 0.06 * repeat_count
                    )
                    p = min(max(p / 2.2, 0.02), 0.97)
                    for _ in range(3):
                        rows.append(_features(detection_type, zone_category, float(confidence), repeat_count))
                        labels.append(1 if rng.random() < p else 0)
    return np.array(rows), np.array(labels)


class _SeverityModel:
    def __init__(self):
        X, y = _synthetic_training_set()
        self.model = LogisticRegression(max_iter=1000)
        self.model.fit(X, y)

    def predict_probability(self, detection_type: str, zone_category: str, confidence: float, repeat_count: int) -> float:
        features = np.array([_features(detection_type, zone_category, confidence, repeat_count)])
        return float(self.model.predict_proba(features)[0][1])


_model: _SeverityModel | None = None


def predict_injury_probability(detection_type: str, zone_category: str, confidence: float, repeat_count: int) -> float:
    global _model
    if _model is None:
        _model = _SeverityModel()
    return _model.predict_probability(detection_type, zone_category, confidence, repeat_count)
