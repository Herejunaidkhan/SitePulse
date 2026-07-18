"""Rules-based risk scoring engine (SitePulse build spec §5).

Deterministic and explainable by design: every score traces back to a detection
type weight, a zone risk multiplier, a confidence multiplier, an optional OSHA
pattern match, a repeat-violation escalation term, and IoT context modifiers
(proximity sensor ground-truth, vitals fatigue proxy). The ML severity layer is
blended in on top, never replacing the rules-based number, so every alert stays
explainable to a safety officer or auditor.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app import db, iot, ml_severity

ML_BLEND_WEIGHT = 0.25  # how much the ML layer nudges the final score, 0-1

BASE_WEIGHT = {
    "ppe_violation": 30.0,
    "proximity": 50.0,
    "fall_risk_posture": 70.0,
    "unguarded_edge": 60.0,
}

ZONE_MULTIPLIER = {
    "low": 0.7,
    "medium": 1.0,
    "high": 1.3,
    "critical": 1.6,
}

CATEGORY_THRESHOLDS = [
    (75, "critical"),
    (50, "high"),
    (25, "medium"),
    (0, "low"),
]

REPEAT_WINDOW_HOURS = 8
REPEAT_ESCALATION_PER_EVENT = 8.0
REPEAT_ESCALATION_CAP = 24.0


def _risk_category(score: float) -> str:
    for threshold, category in CATEGORY_THRESHOLDS:
        if score >= threshold:
            return category
    return "low"


def _matching_osha_pattern(session: Session, detection_type: str) -> db.OshaIncidentPattern | None:
    patterns = session.query(db.OshaIncidentPattern).all()
    for pattern in patterns:
        types = [t.strip() for t in (pattern.correlated_detection_types or "").split(",")]
        if detection_type in types:
            return pattern
    return None


def _repeat_offense_bonus(session: Session, detection: db.Detection) -> tuple[float, int]:
    if not detection.worker_id:
        return 0.0, 0
    since = detection.timestamp - dt.timedelta(hours=REPEAT_WINDOW_HOURS)
    recent = (
        session.query(db.RiskEvent)
        .join(db.Detection, db.Detection.risk_event_id == db.RiskEvent.id)
        .filter(
            db.Detection.worker_id == detection.worker_id,
            db.RiskEvent.created_at >= since,
        )
        .count()
    )
    bonus = min(recent * REPEAT_ESCALATION_PER_EVENT, REPEAT_ESCALATION_CAP)
    return bonus, recent


def score_detection(session: Session, detection: db.Detection) -> db.RiskEvent:
    """Score a single detection and persist the resulting risk_event, linked back to it."""
    zone = session.get(db.Zone, detection.zone_id) if detection.zone_id else None
    zone_category = zone.risk_category if zone else "medium"

    base = BASE_WEIGHT.get(detection.detection_type, 20.0)
    zone_mult = ZONE_MULTIPLIER.get(zone_category, 1.0)
    pattern = _matching_osha_pattern(session, detection.detection_type)
    pattern_bonus = pattern.base_severity_weight * 0.5 if pattern else 0.0
    repeat_bonus, repeat_count = _repeat_offense_bonus(session, detection)

    proximity_confirmation = None
    if detection.detection_type == "proximity":
        proximity_confirmation = iot.latest_proximity_confirmation(session, detection.site_id, detection.equipment_id)
    proximity_bonus = 15.0 if proximity_confirmation else 0.0

    fatigue = iot.latest_fatigue_proxy(session, detection.worker_id)
    fatigue_bonus = 8.0 if fatigue else 0.0

    rules_score = base * zone_mult * detection.confidence_score + pattern_bonus + repeat_bonus + proximity_bonus + fatigue_bonus
    rules_score = min(rules_score, 100.0)

    ml_probability = ml_severity.predict_injury_probability(
        detection.detection_type, zone_category, detection.confidence_score, repeat_count,
    )
    blended_score = (1 - ML_BLEND_WEIGHT) * rules_score + ML_BLEND_WEIGHT * (ml_probability * 100.0)
    score = round(min(blended_score, 100.0), 1)
    category = _risk_category(score)

    explanation_parts = [
        f"{detection.detection_type.replace('_', ' ')} detected with {detection.confidence_score:.0%} confidence",
        f"in a '{zone_category}' risk zone" + (f" ({zone.name})" if zone else ""),
    ]
    if pattern:
        explanation_parts.append(f"matches OSHA pattern '{pattern.pattern_name}' ({pattern.source_citation})")
    if repeat_count:
        explanation_parts.append(f"{repeat_count} prior event(s) for this worker in the last {REPEAT_WINDOW_HOURS}h (+{repeat_bonus:.0f} escalation)")
    if proximity_confirmation:
        explanation_parts.append(f"IoT proximity sensor confirms {proximity_confirmation['distance_m']}m separation (+{proximity_bonus:.0f})")
    if fatigue:
        explanation_parts.append(f"worker fatigue proxy elevated (HR {fatigue['heart_rate']}, {fatigue['shift_minutes']}min shift, +{fatigue_bonus:.0f}, not a medical diagnosis)")
    explanation_parts.append(f"ML severity layer estimates {ml_probability:.0%} injury probability (blended {ML_BLEND_WEIGHT:.0%})")
    explanation = "; ".join(explanation_parts) + f". Score {score}/100 -> {category}."

    risk_event = db.RiskEvent(
        id=db.new_id("risk"),
        site_id=detection.site_id,
        zone_id=detection.zone_id,
        risk_score=score,
        risk_category=category,
        explanation=explanation,
        osha_pattern_id=pattern.id if pattern else None,
        status="open",
    )
    session.add(risk_event)
    session.flush()

    detection.risk_event_id = risk_event.id
    session.flush()

    return risk_event
