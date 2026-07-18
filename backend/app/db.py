"""Multi-tenant schema per SitePulse build spec §3.

Uses Postgres (e.g. Supabase) in production via DATABASE_URL, falling back to a
local SQLite file when unset so `python -m app.seed` still works with no setup.
"""
from __future__ import annotations

import datetime as dt
import os
import uuid

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sitepulse.db")
_env_url = os.environ.get("DATABASE_URL", "").strip()
if _env_url:
    # Supabase gives postgres:// — SQLAlchemy 2.x wants the postgresql:// scheme.
    DATABASE_URL = _env_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DATABASE_URL = f"sqlite:///{_DB_PATH}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def now() -> dt.datetime:
    return dt.datetime.utcnow()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------- org / site
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    tier = Column(String, default="standard")
    billing_plan_id = Column(String, ForeignKey("billing_plans.id"), nullable=True)
    insurer_api_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)

    users = relationship("User", back_populates="org")
    sites = relationship("Site", back_populates="org")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    site_id = Column(String, ForeignKey("sites.id"), nullable=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="foreman")  # admin|safety_officer|foreman|worker
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)

    org = relationship("Organization", back_populates="users")


class Site(Base):
    __tablename__ = "sites"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    name = Column(String, nullable=False)
    address = Column(String, default="")
    timezone = Column(String, default="UTC")
    status = Column(String, default="active")  # onboarding|active|paused
    onboarding_stage = Column(String, default="live")  # inventory|calibration|routing|live
    data_retention_days = Column(Integer, default=90)

    org = relationship("Organization", back_populates="sites")
    zones = relationship("Zone", back_populates="site")


class Zone(Base):
    __tablename__ = "zones"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    name = Column(String, nullable=False)
    zone_type = Column(String, default="general")  # general|edge|crane_swing|confined_space
    risk_category = Column(String, default="medium")  # low|medium|high|critical

    site = relationship("Site", back_populates="zones")


class Camera(Base):
    __tablename__ = "cameras"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    type = Column(String, default="fixed")  # fixed|wearable
    install_location = Column(String, default="")
    calibration_status = Column(String, default="calibrated")
    last_heartbeat = Column(DateTime, default=now)
    status = Column(String, default="online")


# ---------------------------------------------------------------- people / assets
class Worker(Base):
    __tablename__ = "workers"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    org_id = Column(String, ForeignKey("organizations.id"))
    name = Column(String, nullable=False)
    trade = Column(String, default="")
    badge_id = Column(String, default="")
    wearable_device_id = Column(String, nullable=True)
    biometric_consent = Column(Boolean, default=False)
    active = Column(Boolean, default=True)


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    type = Column(String, default="")
    operating_state = Column(String, default="idle")  # idle|active


class PPERequirement(Base):
    __tablename__ = "ppe_requirements"
    id = Column(String, primary_key=True)
    zone_id = Column(String, ForeignKey("zones.id"))
    ppe_type = Column(String, nullable=False)  # hard_hat|hi_vis_vest|safety_glasses|gloves|harness
    trade_applicability = Column(String, default="all")


# ---------------------------------------------------------------- detection & risk
class OshaIncidentPattern(Base):
    __tablename__ = "osha_incident_patterns"
    id = Column(String, primary_key=True)
    pattern_name = Column(String, nullable=False)
    description = Column(Text, default="")
    correlated_detection_types = Column(String, default="")  # comma-separated
    base_severity_weight = Column(Float, default=10.0)
    source_citation = Column(String, default="")


class Detection(Base):
    __tablename__ = "detections"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=True)
    timestamp = Column(DateTime, default=now)
    detection_type = Column(String, nullable=False)  # ppe_violation|proximity|fall_risk_posture|unguarded_edge
    bounding_boxes_json = Column(Text, default="[]")
    confidence_score = Column(Float, default=0.0)
    worker_id = Column(String, ForeignKey("workers.id"), nullable=True)
    equipment_id = Column(String, ForeignKey("equipment.id"), nullable=True)
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    frame_snapshot_url = Column(String, nullable=True)
    model_version = Column(String, default="stub-cv-v0")
    risk_event_id = Column(String, ForeignKey("risk_events.id"), nullable=True)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    risk_score = Column(Float, default=0.0)
    risk_category = Column(String, default="low")  # low|medium|high|critical
    explanation = Column(Text, default="")
    osha_pattern_id = Column(String, ForeignKey("osha_incident_patterns.id"), nullable=True)
    status = Column(String, default="open")  # open|acknowledged|intervention_logged|resolved|false_positive
    created_at = Column(DateTime, default=now)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, ForeignKey("users.id"), nullable=True)
    intervention_notes = Column(Text, nullable=True)


# ---------------------------------------------------------------- tracking system
class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True)
    risk_event_id = Column(String, ForeignKey("risk_events.id"))
    channel = Column(String, default="dashboard")  # push|sms|dashboard
    recipient_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    sent_at = Column(DateTime, default=now)
    delivered_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    response_time_seconds = Column(Float, nullable=True)


class IncidentLog(Base):
    __tablename__ = "incident_log"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    risk_event_id = Column(String, ForeignKey("risk_events.id"), nullable=True)
    type = Column(String, default="near_miss")  # near_miss|actual_incident|violation
    description = Column(Text, default="")
    reported_by = Column(String, ForeignKey("users.id"), nullable=True)
    severity = Column(String, default="low")
    injury_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class AuditTrail(Base):
    """Append-only. `prev_hash`/`row_hash` form a hash chain so any row tampering
    or deletion breaks verification (§6.3 tamper-evident requirement)."""
    __tablename__ = "audit_trail"
    id = Column(String, primary_key=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    before_state_json = Column(Text, nullable=True)
    after_state_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=now)
    prev_hash = Column(String, nullable=True)
    row_hash = Column(String, nullable=True)


class CalibrationLog(Base):
    __tablename__ = "calibration_log"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    threshold_type = Column(String, nullable=False)
    old_value = Column(String, default="")
    new_value = Column(String, default="")
    changed_by = Column(String, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=now)
    justification = Column(Text, default="")


# ---------------------------------------------------------------- IoT sensors
class IotSensor(Base):
    __tablename__ = "iot_sensors"
    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"))
    type = Column(String, nullable=False)  # proximity|vitals|env
    equipment_id = Column(String, ForeignKey("equipment.id"), nullable=True)
    worker_id = Column(String, ForeignKey("workers.id"), nullable=True)
    last_reading_at = Column(DateTime, nullable=True)
    battery_level = Column(Float, default=100.0)
    status = Column(String, default="online")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(String, primary_key=True)
    sensor_id = Column(String, ForeignKey("iot_sensors.id"))
    timestamp = Column(DateTime, default=now)
    value_json = Column(Text, default="{}")  # e.g. {"distance_m": 1.2} or {"heart_rate": 142, "shift_minutes": 380}


# ---------------------------------------------------------------- location tracking
class WorkerLocationTrail(Base):
    __tablename__ = "worker_location_trail"
    id = Column(String, primary_key=True)
    worker_id = Column(String, ForeignKey("workers.id"))
    site_id = Column(String, ForeignKey("sites.id"))
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    timestamp = Column(DateTime, default=now)
    source = Column(String, default="wearable")  # wearable|camera_reid


# ---------------------------------------------------------------- billing
class BillingPlan(Base):
    __tablename__ = "billing_plans"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    base_fee = Column(Float, default=500.0)
    camera_unit_price = Column(Float, default=45.0)
    sensor_unit_price = Column(Float, default=15.0)


class UsagePeriod(Base):
    """One row per org per billing period; usage counted at invoice time (§10 metering)."""
    __tablename__ = "usage_periods"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    camera_count = Column(Integer, default=0)
    sensor_count = Column(Integer, default=0)
    computed_total = Column(Float, default=0.0)
    created_at = Column(DateTime, default=now)


# ---------------------------------------------------------------- EMR / insurer analytics
class IncidentPreventionBonus(Base):
    __tablename__ = "incident_prevention_bonus"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    risk_event_id = Column(String, ForeignKey("risk_events.id"))
    estimated_severity_avoided = Column(String, default="")
    bonus_amount = Column(Float, default=0.0)
    verification_status = Column(String, default="pending")  # pending|verified|disputed|rejected
    verified_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)


class EmrAnalyticsSnapshot(Base):
    __tablename__ = "emr_analytics"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"))
    period = Column(String, nullable=False)  # e.g. "2026-Q3"
    computed_emr_delta = Column(Float, default=0.0)
    incidents_prevented_count = Column(Integer, default=0)
    exposure_hours = Column(Float, default=0.0)
    created_at = Column(DateTime, default=now)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
