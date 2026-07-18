"""Stubbed CV inference service.

Real detection models (PPE, proximity, fall-risk posture, unguarded edge) plug in
behind `simulate_detection` later — callers only depend on this function's signature,
never on how a frame gets turned into a detection.
"""
from __future__ import annotations

import json
import random

from sqlalchemy.orm import Session

from app import db

DETECTION_TYPES = ["ppe_violation", "proximity", "fall_risk_posture", "unguarded_edge"]

MODEL_VERSION = "stub-cv-v0.1"


def simulate_detection(
    session: Session,
    site_id: str,
    detection_type: str | None = None,
    zone_id: str | None = None,
    worker_id: str | None = None,
    confidence_score: float | None = None,
) -> db.Detection:
    """Generate one synthetic detection event, as if a CV model just ran inference on a frame."""
    detection_type = detection_type or random.choice(DETECTION_TYPES)

    if zone_id is None:
        zones = session.query(db.Zone).filter(db.Zone.site_id == site_id).all()
        zone_id = random.choice(zones).id if zones else None

    if worker_id is None:
        workers = session.query(db.Worker).filter(db.Worker.site_id == site_id, db.Worker.active.is_(True)).all()
        worker_id = random.choice(workers).id if workers else None

    equipment_id = None
    if detection_type == "proximity":
        equipment = session.query(db.Equipment).filter(db.Equipment.site_id == site_id).all()
        equipment_id = random.choice(equipment).id if equipment else None

    confidence = confidence_score if confidence_score is not None else round(random.uniform(0.55, 0.98), 2)

    bbox = [{"x": random.randint(0, 800), "y": random.randint(0, 600), "w": random.randint(40, 200), "h": random.randint(60, 260)}]

    detection = db.Detection(
        id=db.new_id("det"),
        site_id=site_id,
        camera_id=None,
        detection_type=detection_type,
        bounding_boxes_json=json.dumps(bbox),
        confidence_score=confidence,
        worker_id=worker_id,
        equipment_id=equipment_id,
        zone_id=zone_id,
        model_version=MODEL_VERSION,
    )
    session.add(detection)
    session.flush()
    return detection
