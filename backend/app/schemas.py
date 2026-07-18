from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    org_id: str
    site_id: str | None
    email: str
    name: str
    role: str

    class Config:
        from_attributes = True


class ZoneOut(BaseModel):
    id: str
    site_id: str
    name: str
    zone_type: str
    risk_category: str

    class Config:
        from_attributes = True


class ZoneCreate(BaseModel):
    name: str
    zone_type: str = "general"
    risk_category: str = "medium"


class WorkerOut(BaseModel):
    id: str
    site_id: str
    name: str
    trade: str
    badge_id: str
    active: bool

    class Config:
        from_attributes = True


class WorkerCreate(BaseModel):
    name: str
    trade: str = ""
    badge_id: str = ""


class SiteOut(BaseModel):
    id: str
    org_id: str
    name: str
    address: str
    status: str

    class Config:
        from_attributes = True


class DetectionOut(BaseModel):
    id: str
    site_id: str
    detection_type: str
    confidence_score: float
    worker_id: str | None
    zone_id: str | None
    equipment_id: str | None
    timestamp: dt.datetime
    model_version: str
    risk_event_id: str | None

    class Config:
        from_attributes = True


class SimulateDetectionRequest(BaseModel):
    detection_type: str | None = None
    zone_id: str | None = None
    worker_id: str | None = None
    confidence_score: float | None = None


class RiskEventOut(BaseModel):
    id: str
    site_id: str
    zone_id: str | None
    risk_score: float
    risk_category: str
    explanation: str
    status: str
    created_at: dt.datetime
    acknowledged_at: dt.datetime | None
    resolved_at: dt.datetime | None
    intervention_notes: str | None

    class Config:
        from_attributes = True


class SimulateDetectionResponse(BaseModel):
    detection: DetectionOut
    risk_event: RiskEventOut
    alerts_created: int


class InterventionRequest(BaseModel):
    description: str
    photo_url: str | None = None


class ResolveRequest(BaseModel):
    status: str  # resolved|false_positive


class AlertOut(BaseModel):
    id: str
    risk_event_id: str
    channel: str
    recipient_user_id: str | None
    sent_at: dt.datetime
    acknowledged_at: dt.datetime | None
    response_time_seconds: float | None

    class Config:
        from_attributes = True


class IncidentLogOut(BaseModel):
    id: str
    site_id: str
    risk_event_id: str | None
    type: str
    description: str
    severity: str
    injury_flag: bool
    created_at: dt.datetime

    class Config:
        from_attributes = True


class IncidentLogCreate(BaseModel):
    type: str = "near_miss"
    description: str
    severity: str = "low"
    injury_flag: bool = False
    risk_event_id: str | None = None


class AuditTrailOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: str | None
    timestamp: dt.datetime

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    open_risk_events: int
    critical_open: int
    high_open: int
    alerts_pending_ack: int
    zone_heat: list[dict]
    mean_time_to_ack_seconds: float | None


# ---------------------------------------------------------------- IoT
class SimulateReadingRequest(BaseModel):
    sensor_type: str  # proximity|vitals
    equipment_id: str | None = None
    worker_id: str | None = None
    value: dict | None = None


class IotSensorOut(BaseModel):
    id: str
    site_id: str
    type: str
    equipment_id: str | None
    worker_id: str | None
    last_reading_at: dt.datetime | None
    battery_level: float
    status: str

    class Config:
        from_attributes = True


class SensorReadingOut(BaseModel):
    id: str
    sensor_id: str
    timestamp: dt.datetime
    value_json: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------- location tracking
class SimulatePingRequest(BaseModel):
    worker_id: str
    zone_id: str | None = None
    source: str = "wearable"


class LocationPingOut(BaseModel):
    id: str
    worker_id: str
    site_id: str
    zone_id: str | None
    timestamp: dt.datetime
    source: str

    class Config:
        from_attributes = True


class DwellTimeEntry(BaseModel):
    zone_id: str
    zone_name: str
    ping_count: int


# ---------------------------------------------------------------- billing
class BillingSummary(BaseModel):
    plan_name: str
    base_fee: float
    camera_count: int
    camera_unit_price: float
    sensor_count: int
    sensor_unit_price: float
    estimated_total: float


# ---------------------------------------------------------------- EMR / insurer
class IncidentBonusOut(BaseModel):
    id: str
    org_id: str
    risk_event_id: str
    estimated_severity_avoided: str
    bonus_amount: float
    verification_status: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class BonusVerifyRequest(BaseModel):
    status: str  # verified|disputed|rejected


class EmrSummary(BaseModel):
    period: str
    org_id: str
    incidents_prevented_count: int
    estimated_bonus_total: float
    resolved_risk_events: int
    open_high_critical_risk_events: int
    exposure_hours: float
    computed_emr_delta: float


# ---------------------------------------------------------------- calibration + onboarding
class CalibrationCreate(BaseModel):
    threshold_type: str
    old_value: str = ""
    new_value: str
    justification: str


class CalibrationLogOut(BaseModel):
    id: str
    site_id: str
    threshold_type: str
    old_value: str
    new_value: str
    changed_by: str | None
    changed_at: dt.datetime
    justification: str

    class Config:
        from_attributes = True


class OnboardingAdvanceRequest(BaseModel):
    stage: str  # inventory|calibration|routing|live
    notes: str = ""


class OnboardingChecklist(BaseModel):
    stage: str
    site_status: str
    camera_count: int
    zone_count: int
    ppe_requirement_count: int
    calibration_entries: int
    users_assigned: int
    ready_for_next_stage: bool


class AuditVerifyResult(BaseModel):
    intact: bool
    broken_at_id: str | None
