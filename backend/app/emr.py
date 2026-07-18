"""Incident-prevention bonus workflow + EMR/insurer analytics (§6.5, §10).

Note: OSHA pattern-matching and any premium-reduction framing here are prototype
placeholders — production severity-avoided dollar figures need real insurer/actuarial
data and legal review before being shown to a customer, per the build spec's closing note.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import db

SEVERITY_DOLLAR_PROXY = 2000.0  # placeholder $/severity-weight-point, NOT an actuarial figure
BONUS_ELIGIBLE_CATEGORIES = {"high", "critical"}


def create_bonus_if_eligible(session: Session, risk_event: db.RiskEvent) -> db.IncidentPreventionBonus | None:
    if risk_event.status != "resolved" or risk_event.risk_category not in BONUS_ELIGIBLE_CATEGORIES:
        return None
    if not risk_event.osha_pattern_id:
        return None

    site = session.get(db.Site, risk_event.site_id)
    pattern = session.get(db.OshaIncidentPattern, risk_event.osha_pattern_id)
    estimated_amount = round(pattern.base_severity_weight * SEVERITY_DOLLAR_PROXY / 10.0, 2)

    bonus = db.IncidentPreventionBonus(
        id=db.new_id("bonus"),
        org_id=site.org_id,
        risk_event_id=risk_event.id,
        estimated_severity_avoided=f"{pattern.pattern_name} ({pattern.source_citation})",
        bonus_amount=estimated_amount,
        verification_status="pending",
    )
    session.add(bonus)
    session.flush()
    return bonus


def update_bonus_status(session: Session, bonus_id: str, status: str, actor_user_id: str) -> db.IncidentPreventionBonus | None:
    bonus = session.get(db.IncidentPreventionBonus, bonus_id)
    if bonus is None:
        return None
    bonus.verification_status = status
    bonus.verified_by = actor_user_id
    session.flush()
    return bonus


def compute_emr_summary(session: Session, org_id: str, period_label: str) -> dict:
    site_ids = [s.id for s in session.query(db.Site.id).filter(db.Site.org_id == org_id)]

    verified_bonuses = (
        session.query(db.IncidentPreventionBonus)
        .filter(db.IncidentPreventionBonus.org_id == org_id, db.IncidentPreventionBonus.verification_status == "verified")
        .all()
    )
    incidents_prevented_count = len(verified_bonuses)
    total_bonus_amount = sum(b.bonus_amount for b in verified_bonuses)

    resolved_events = (
        session.query(db.RiskEvent)
        .filter(db.RiskEvent.site_id.in_(site_ids), db.RiskEvent.status == "resolved")
        .count()
        if site_ids else 0
    )
    open_high_critical = (
        session.query(db.RiskEvent)
        .filter(
            db.RiskEvent.site_id.in_(site_ids),
            db.RiskEvent.status.in_(["open", "acknowledged", "intervention_logged"]),
            db.RiskEvent.risk_category.in_(["high", "critical"]),
        )
        .count()
        if site_ids else 0
    )
    worker_count = session.query(db.Worker).filter(db.Worker.site_id.in_(site_ids), db.Worker.active.is_(True)).count() if site_ids else 0
    exposure_hours = worker_count * 8.0  # proxy: active workers x one shift; real figure needs timeclock integration

    # simple downward-trending proxy: fewer unresolved high/critical events relative to exposure => lower EMR delta
    computed_emr_delta = round(-0.01 * incidents_prevented_count + 0.02 * open_high_critical, 4)

    return {
        "period": period_label,
        "org_id": org_id,
        "incidents_prevented_count": incidents_prevented_count,
        "estimated_bonus_total": round(total_bonus_amount, 2),
        "resolved_risk_events": resolved_events,
        "open_high_critical_risk_events": open_high_critical,
        "exposure_hours": exposure_hours,
        "computed_emr_delta": computed_emr_delta,
    }


def save_snapshot(session: Session, summary: dict) -> db.EmrAnalyticsSnapshot:
    snapshot = db.EmrAnalyticsSnapshot(
        id=db.new_id("emr"),
        org_id=summary["org_id"],
        period=summary["period"],
        computed_emr_delta=summary["computed_emr_delta"],
        incidents_prevented_count=summary["incidents_prevented_count"],
        exposure_hours=summary["exposure_hours"],
    )
    session.add(snapshot)
    session.flush()
    return snapshot
