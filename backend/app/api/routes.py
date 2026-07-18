from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import alerting, auth, billing, cv_stub, db, emr, iot, location, risk_engine, schemas

router = APIRouter(prefix="/api")


def get_db():
    yield from db.get_session()


def _site_or_404(session: Session, site_id: str, user: db.User) -> db.Site:
    site = session.get(db.Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    auth.assert_site_access(user, site)
    return site


# ---------------------------------------------------------------- auth
@router.post("/auth/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, session: Session = Depends(get_db)):
    user = session.query(db.User).filter(db.User.email == payload.email).first()
    if user is None or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    token = auth.create_token(user)
    return schemas.LoginResponse(token=token, user=schemas.UserOut.model_validate(user))


@router.get("/auth/me", response_model=schemas.UserOut)
def me(user: db.User = Depends(auth.current_user)):
    return user


# ---------------------------------------------------------------- sites
@router.get("/sites", response_model=list[schemas.SiteOut])
def list_sites(session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    return session.query(db.Site).filter(db.Site.org_id == user.org_id).all()


@router.get("/sites/{site_id}", response_model=schemas.SiteOut)
def get_site(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    return _site_or_404(session, site_id, user)


@router.get("/sites/{site_id}/zones", response_model=list[schemas.ZoneOut])
def list_zones(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return session.query(db.Zone).filter(db.Zone.site_id == site_id).all()


@router.post("/sites/{site_id}/zones", response_model=schemas.ZoneOut)
def create_zone(
    site_id: str,
    payload: schemas.ZoneCreate,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    _site_or_404(session, site_id, user)
    zone = db.Zone(id=db.new_id("zone"), site_id=site_id, **payload.model_dump())
    session.add(zone)
    session.commit()
    return zone


@router.get("/sites/{site_id}/workers", response_model=list[schemas.WorkerOut])
def list_workers(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return session.query(db.Worker).filter(db.Worker.site_id == site_id).all()


@router.post("/sites/{site_id}/workers", response_model=schemas.WorkerOut)
def create_worker(
    site_id: str,
    payload: schemas.WorkerCreate,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    site = _site_or_404(session, site_id, user)
    worker = db.Worker(id=db.new_id("worker"), site_id=site_id, org_id=site.org_id, **payload.model_dump())
    session.add(worker)
    session.commit()
    return worker


# ---------------------------------------------------------------- detections (CV stub)
@router.post("/sites/{site_id}/detections/simulate", response_model=schemas.SimulateDetectionResponse)
def simulate_detection(
    site_id: str,
    payload: schemas.SimulateDetectionRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    detection = cv_stub.simulate_detection(
        session,
        site_id=site_id,
        detection_type=payload.detection_type,
        zone_id=payload.zone_id,
        worker_id=payload.worker_id,
        confidence_score=payload.confidence_score,
    )
    risk_event = risk_engine.score_detection(session, detection)
    alerts = alerting.create_alerts_for_risk_event(session, risk_event)
    alerting.record_audit(session, "detection", detection.id, "created", user.id, after={"detection_type": detection.detection_type})
    session.commit()
    return schemas.SimulateDetectionResponse(
        detection=schemas.DetectionOut.model_validate(detection),
        risk_event=schemas.RiskEventOut.model_validate(risk_event),
        alerts_created=len(alerts),
    )


@router.get("/sites/{site_id}/detections", response_model=list[schemas.DetectionOut])
def list_detections(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return (
        session.query(db.Detection)
        .filter(db.Detection.site_id == site_id)
        .order_by(db.Detection.timestamp.desc())
        .limit(100)
        .all()
    )


# ---------------------------------------------------------------- risk events
@router.get("/sites/{site_id}/risk-events", response_model=list[schemas.RiskEventOut])
def list_risk_events(
    site_id: str,
    status: str | None = None,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    q = session.query(db.RiskEvent).filter(db.RiskEvent.site_id == site_id)
    if status:
        q = q.filter(db.RiskEvent.status == status)
    return q.order_by(db.RiskEvent.created_at.desc()).limit(200).all()


def _risk_event_or_404(session: Session, risk_event_id: str, user: db.User) -> db.RiskEvent:
    risk_event = session.get(db.RiskEvent, risk_event_id)
    if risk_event is None:
        raise HTTPException(404, "Risk event not found")
    site = session.get(db.Site, risk_event.site_id)
    auth.assert_site_access(user, site)
    return risk_event


@router.post("/risk-events/{risk_event_id}/acknowledge", response_model=schemas.RiskEventOut)
def acknowledge_risk_event(risk_event_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    risk_event = _risk_event_or_404(session, risk_event_id, user)
    before = {"status": risk_event.status}
    risk_event.status = "acknowledged"
    risk_event.acknowledged_at = db.now()
    for alert in session.query(db.Alert).filter(db.Alert.risk_event_id == risk_event_id, db.Alert.recipient_user_id == user.id):
        if alert.acknowledged_at is None:
            alert.acknowledged_at = db.now()
            alert.response_time_seconds = (alert.acknowledged_at - alert.sent_at).total_seconds()
    alerting.record_audit(session, "risk_event", risk_event.id, "acknowledged", user.id, before=before, after={"status": risk_event.status})
    session.commit()
    return risk_event


@router.post("/risk-events/{risk_event_id}/log-intervention", response_model=schemas.RiskEventOut)
def log_intervention(
    risk_event_id: str,
    payload: schemas.InterventionRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    risk_event = _risk_event_or_404(session, risk_event_id, user)
    before = {"status": risk_event.status}
    risk_event.status = "intervention_logged"
    risk_event.intervention_notes = payload.description
    alerting.record_audit(session, "risk_event", risk_event.id, "intervention_logged", user.id, before=before, after={"description": payload.description})
    session.commit()
    return risk_event


@router.post("/risk-events/{risk_event_id}/resolve", response_model=schemas.RiskEventOut)
def resolve_risk_event(
    risk_event_id: str,
    payload: schemas.ResolveRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    if payload.status not in ("resolved", "false_positive"):
        raise HTTPException(400, "status must be 'resolved' or 'false_positive'")
    risk_event = _risk_event_or_404(session, risk_event_id, user)
    before = {"status": risk_event.status}
    risk_event.status = payload.status
    risk_event.resolved_at = db.now()
    risk_event.resolved_by = user.id
    alerting.record_audit(session, "risk_event", risk_event.id, payload.status, user.id, before=before, after={"status": payload.status})
    if payload.status == "resolved":
        emr.create_bonus_if_eligible(session, risk_event)
    session.commit()
    return risk_event


# ---------------------------------------------------------------- alerts
@router.get("/sites/{site_id}/alerts", response_model=list[schemas.AlertOut])
def list_alerts(
    site_id: str,
    unacknowledged_only: bool = False,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    q = (
        session.query(db.Alert)
        .join(db.RiskEvent, db.Alert.risk_event_id == db.RiskEvent.id)
        .filter(db.RiskEvent.site_id == site_id)
    )
    if unacknowledged_only:
        q = q.filter(db.Alert.acknowledged_at.is_(None))
    return q.order_by(db.Alert.sent_at.desc()).limit(200).all()


# ---------------------------------------------------------------- incident log
@router.get("/sites/{site_id}/incidents", response_model=list[schemas.IncidentLogOut])
def list_incidents(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return (
        session.query(db.IncidentLog)
        .filter(db.IncidentLog.site_id == site_id)
        .order_by(db.IncidentLog.created_at.desc())
        .all()
    )


@router.post("/sites/{site_id}/incidents", response_model=schemas.IncidentLogOut)
def create_incident(
    site_id: str,
    payload: schemas.IncidentLogCreate,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    incident = db.IncidentLog(
        id=db.new_id("incident"),
        site_id=site_id,
        reported_by=user.id,
        **payload.model_dump(),
    )
    session.add(incident)
    alerting.record_audit(session, "incident_log", incident.id, "created", user.id, after={"type": incident.type})
    session.commit()
    return incident


# ---------------------------------------------------------------- audit trail
@router.get("/sites/{site_id}/audit-trail", response_model=list[schemas.AuditTrailOut])
def list_audit_trail(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    # audit_trail is entity-agnostic; scope to risk events / detections / incidents belonging to this site
    risk_event_ids = [r.id for r in session.query(db.RiskEvent.id).filter(db.RiskEvent.site_id == site_id)]
    detection_ids = [d.id for d in session.query(db.Detection.id).filter(db.Detection.site_id == site_id)]
    incident_ids = [i.id for i in session.query(db.IncidentLog.id).filter(db.IncidentLog.site_id == site_id)]
    all_ids = set(risk_event_ids) | set(detection_ids) | set(incident_ids)
    return (
        session.query(db.AuditTrail)
        .filter(db.AuditTrail.entity_id.in_(all_ids))
        .order_by(db.AuditTrail.timestamp.desc())
        .limit(200)
        .all()
    )


# ---------------------------------------------------------------- osha patterns
@router.get("/osha-patterns")
def list_osha_patterns(session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    patterns = session.query(db.OshaIncidentPattern).all()
    return [
        {
            "id": p.id,
            "pattern_name": p.pattern_name,
            "description": p.description,
            "correlated_detection_types": p.correlated_detection_types,
            "base_severity_weight": p.base_severity_weight,
            "source_citation": p.source_citation,
        }
        for p in patterns
    ]


# ---------------------------------------------------------------- dashboard
@router.get("/sites/{site_id}/dashboard-summary", response_model=schemas.DashboardSummary)
def dashboard_summary(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    open_events = session.query(db.RiskEvent).filter(
        db.RiskEvent.site_id == site_id,
        db.RiskEvent.status.in_(["open", "acknowledged", "intervention_logged"]),
    ).all()

    zone_scores: dict[str, list[float]] = {}
    for event in open_events:
        zone_scores.setdefault(event.zone_id or "unassigned", []).append(event.risk_score)

    zones = {z.id: z.name for z in session.query(db.Zone).filter(db.Zone.site_id == site_id)}
    zone_heat = [
        {"zone_id": zid, "zone_name": zones.get(zid, "Unassigned"), "avg_risk_score": round(sum(scores) / len(scores), 1), "open_count": len(scores)}
        for zid, scores in zone_scores.items()
    ]

    ack_times = [
        (a.acknowledged_at - a.sent_at).total_seconds()
        for a in session.query(db.Alert).join(db.RiskEvent, db.Alert.risk_event_id == db.RiskEvent.id)
        .filter(db.RiskEvent.site_id == site_id, db.Alert.acknowledged_at.isnot(None))
    ]

    return schemas.DashboardSummary(
        open_risk_events=len(open_events),
        critical_open=len([e for e in open_events if e.risk_category == "critical"]),
        high_open=len([e for e in open_events if e.risk_category == "high"]),
        alerts_pending_ack=session.query(db.Alert).join(db.RiskEvent, db.Alert.risk_event_id == db.RiskEvent.id)
            .filter(db.RiskEvent.site_id == site_id, db.Alert.acknowledged_at.is_(None)).count(),
        zone_heat=zone_heat,
        mean_time_to_ack_seconds=round(sum(ack_times) / len(ack_times), 1) if ack_times else None,
    )


# ---------------------------------------------------------------- IoT sensors
@router.post("/sites/{site_id}/iot-sensors/simulate-reading", response_model=schemas.SensorReadingOut)
def simulate_sensor_reading(
    site_id: str,
    payload: schemas.SimulateReadingRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    reading = iot.simulate_reading(
        session, site_id, payload.sensor_type,
        equipment_id=payload.equipment_id, worker_id=payload.worker_id, value=payload.value,
    )
    session.commit()
    return reading


@router.get("/sites/{site_id}/iot-sensors", response_model=list[schemas.IotSensorOut])
def list_iot_sensors(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return session.query(db.IotSensor).filter(db.IotSensor.site_id == site_id).all()


# ---------------------------------------------------------------- location tracking
@router.post("/sites/{site_id}/location/simulate-ping", response_model=schemas.LocationPingOut)
def simulate_location_ping(
    site_id: str,
    payload: schemas.SimulatePingRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    ping = location.simulate_ping(session, site_id, payload.worker_id, payload.zone_id, payload.source)
    session.commit()
    return ping


@router.get("/sites/{site_id}/location/trail", response_model=list[schemas.LocationPingOut])
def location_trail(
    site_id: str,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
    zone_id: str | None = None,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.current_user),
):
    _site_or_404(session, site_id, user)
    start = start or (db.now() - dt.timedelta(hours=24))
    end = end or db.now()
    return location.trail_for_range(session, site_id, start, end, zone_id)


@router.get("/sites/{site_id}/location/dwell-time", response_model=list[schemas.DwellTimeEntry])
def dwell_time(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return location.dwell_time_by_zone(session, site_id)


# ---------------------------------------------------------------- billing
@router.get("/billing/summary", response_model=schemas.BillingSummary)
def billing_summary(
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin")),
):
    return billing.current_usage(session, user.org_id)


# ---------------------------------------------------------------- EMR / incident-prevention bonus / insurer API
@router.get("/orgs/{org_id}/incident-bonuses", response_model=list[schemas.IncidentBonusOut])
def list_incident_bonuses(
    org_id: str,
    status: str | None = None,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    if org_id != user.org_id:
        raise HTTPException(403, "Not your organization")
    q = session.query(db.IncidentPreventionBonus).filter(db.IncidentPreventionBonus.org_id == org_id)
    if status:
        q = q.filter(db.IncidentPreventionBonus.verification_status == status)
    return q.order_by(db.IncidentPreventionBonus.created_at.desc()).all()


@router.post("/incident-bonuses/{bonus_id}/verify", response_model=schemas.IncidentBonusOut)
def verify_incident_bonus(
    bonus_id: str,
    payload: schemas.BonusVerifyRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    if payload.status not in ("verified", "disputed", "rejected"):
        raise HTTPException(400, "status must be verified, disputed, or rejected")
    bonus = session.get(db.IncidentPreventionBonus, bonus_id)
    if bonus is None or bonus.org_id != user.org_id:
        raise HTTPException(404, "Bonus record not found")
    before = {"verification_status": bonus.verification_status}
    bonus = emr.update_bonus_status(session, bonus_id, payload.status, user.id)
    alerting.record_audit(session, "incident_prevention_bonus", bonus.id, payload.status, user.id, before=before, after={"verification_status": payload.status})
    session.commit()
    return bonus


@router.get("/orgs/{org_id}/emr-summary", response_model=schemas.EmrSummary)
def emr_summary(
    org_id: str,
    period: str = "current",
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    if org_id != user.org_id:
        raise HTTPException(403, "Not your organization")
    return emr.compute_emr_summary(session, org_id, period)


@router.post("/orgs/{org_id}/emr-snapshot", response_model=schemas.EmrSummary)
def save_emr_snapshot(
    org_id: str,
    period: str,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin")),
):
    if org_id != user.org_id:
        raise HTTPException(403, "Not your organization")
    summary = emr.compute_emr_summary(session, org_id, period)
    emr.save_snapshot(session, summary)
    alerting.record_audit(session, "emr_analytics", org_id, "snapshot_saved", user.id, after={"period": period})
    session.commit()
    return summary


@router.get("/insurer/{org_id}/report", response_model=schemas.EmrSummary)
def insurer_report(
    org_id: str,
    period: str = "current",
    x_insurer_key: str = Header(default=""),
    session: Session = Depends(get_db),
):
    """Read-only, API-key-scoped — no JWT/user session required (§6.5 insurer/GC reporting API)."""
    org = session.get(db.Organization, org_id)
    if org is None or not org.insurer_api_key or x_insurer_key != org.insurer_api_key:
        raise HTTPException(401, "Invalid or missing insurer API key")
    return emr.compute_emr_summary(session, org_id, period)


# ---------------------------------------------------------------- calibration + onboarding
@router.get("/sites/{site_id}/calibration-log", response_model=list[schemas.CalibrationLogOut])
def list_calibration_log(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    _site_or_404(session, site_id, user)
    return session.query(db.CalibrationLog).filter(db.CalibrationLog.site_id == site_id).order_by(db.CalibrationLog.changed_at.desc()).all()


@router.post("/sites/{site_id}/calibration-log", response_model=schemas.CalibrationLogOut)
def create_calibration_entry(
    site_id: str,
    payload: schemas.CalibrationCreate,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    _site_or_404(session, site_id, user)
    entry = db.CalibrationLog(id=db.new_id("calib"), site_id=site_id, changed_by=user.id, **payload.model_dump())
    session.add(entry)
    alerting.record_audit(session, "calibration_log", entry.id, "threshold_changed", user.id, after={"threshold_type": entry.threshold_type, "new_value": entry.new_value})
    session.commit()
    return entry


@router.get("/sites/{site_id}/onboarding-checklist", response_model=schemas.OnboardingChecklist)
def onboarding_checklist(site_id: str, session: Session = Depends(get_db), user: db.User = Depends(auth.current_user)):
    site = _site_or_404(session, site_id, user)
    camera_count = session.query(db.Camera).filter(db.Camera.site_id == site_id).count()
    zone_count = session.query(db.Zone).filter(db.Zone.site_id == site_id).count()
    ppe_count = (
        session.query(db.PPERequirement)
        .join(db.Zone, db.PPERequirement.zone_id == db.Zone.id)
        .filter(db.Zone.site_id == site_id)
        .count()
    )
    calibration_count = session.query(db.CalibrationLog).filter(db.CalibrationLog.site_id == site_id).count()
    users_assigned = session.query(db.User).filter(db.User.site_id == site_id).count()

    ready = {
        "inventory": camera_count > 0 and zone_count > 0 and ppe_count > 0,
        "calibration": calibration_count > 0,
        "routing": users_assigned > 0,
        "live": True,
    }.get(site.onboarding_stage, False)

    return schemas.OnboardingChecklist(
        stage=site.onboarding_stage,
        site_status=site.status,
        camera_count=camera_count,
        zone_count=zone_count,
        ppe_requirement_count=ppe_count,
        calibration_entries=calibration_count,
        users_assigned=users_assigned,
        ready_for_next_stage=ready,
    )


@router.post("/sites/{site_id}/onboarding/advance", response_model=schemas.OnboardingChecklist)
def advance_onboarding(
    site_id: str,
    payload: schemas.OnboardingAdvanceRequest,
    session: Session = Depends(get_db),
    user: db.User = Depends(auth.require_role("admin", "safety_officer")),
):
    site = _site_or_404(session, site_id, user)
    if payload.stage not in ("inventory", "calibration", "routing", "live"):
        raise HTTPException(400, "invalid stage")
    before = {"onboarding_stage": site.onboarding_stage, "status": site.status}
    site.onboarding_stage = payload.stage
    if payload.stage == "live":
        site.status = "active"
    alerting.record_audit(session, "site", site.id, f"onboarding_advanced_to_{payload.stage}", user.id, before=before, after={"stage": payload.stage, "notes": payload.notes})
    session.commit()
    return onboarding_checklist(site_id, session, user)


# ---------------------------------------------------------------- audit trail integrity
@router.get("/audit-trail/verify", response_model=schemas.AuditVerifyResult)
def verify_audit_trail(session: Session = Depends(get_db), user: db.User = Depends(auth.require_role("admin"))):
    intact, broken_at_id = alerting.verify_audit_chain(session)
    return schemas.AuditVerifyResult(intact=intact, broken_at_id=broken_at_id)
