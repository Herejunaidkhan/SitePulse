"""Alerting service (SitePulse build spec §7) + audit trail helper (§6.3)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from sqlalchemy.orm import Session

from app import db

IMMEDIATE_ALERT_CATEGORIES = {"high", "critical"}


def _recipients_for(session: Session, risk_event: db.RiskEvent) -> list[db.User]:
    site = session.get(db.Site, risk_event.site_id)
    roles = ["safety_officer", "admin"]
    if risk_event.risk_category == "critical":
        roles.append("foreman")
    return (
        session.query(db.User)
        .filter(
            db.User.org_id == site.org_id,
            db.User.active.is_(True),
            db.User.role.in_(roles),
        )
        .filter((db.User.site_id == site.id) | (db.User.site_id.is_(None)))
        .all()
    )


def create_alerts_for_risk_event(session: Session, risk_event: db.RiskEvent) -> list[db.Alert]:
    """Fan out a dashboard alert to every relevant recipient if the risk category warrants it."""
    if risk_event.risk_category not in IMMEDIATE_ALERT_CATEGORIES:
        return []

    alerts = []
    for user in _recipients_for(session, risk_event):
        alert = db.Alert(
            id=db.new_id("alert"),
            risk_event_id=risk_event.id,
            channel="dashboard",
            recipient_user_id=user.id,
            sent_at=db.now(),
            delivered_at=db.now(),
        )
        session.add(alert)
        alerts.append(alert)
    session.flush()
    return alerts


def record_audit(
    session: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_user_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
) -> db.AuditTrail:
    """Append a row and chain it to the prior row's hash — deleting or editing any
    earlier row breaks every hash after it, making tampering detectable (§6.3)."""
    last = session.query(db.AuditTrail).order_by(db.AuditTrail.timestamp.desc(), db.AuditTrail.id.desc()).first()
    prev_hash = last.row_hash if last else "genesis"
    timestamp = db.now()
    before_json = json.dumps(before) if before is not None else None
    after_json = json.dumps(after) if after is not None else None

    row_hash = hashlib.sha256(
        "|".join([
            entity_type, entity_id, action, actor_user_id or "",
            before_json or "", after_json or "", timestamp.isoformat(), prev_hash,
        ]).encode()
    ).hexdigest()

    entry = db.AuditTrail(
        id=db.new_id("audit"),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor_user_id,
        before_state_json=before_json,
        after_state_json=after_json,
        timestamp=timestamp,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
    session.add(entry)
    session.flush()
    return entry


def verify_audit_chain(session: Session) -> tuple[bool, str | None]:
    """Recompute every row's hash in order; the first mismatch names the break point."""
    rows = session.query(db.AuditTrail).order_by(db.AuditTrail.timestamp.asc(), db.AuditTrail.id.asc()).all()
    expected_prev = "genesis"
    for row in rows:
        recomputed = hashlib.sha256(
            "|".join([
                row.entity_type, row.entity_id, row.action, row.actor_user_id or "",
                row.before_state_json or "", row.after_state_json or "", row.timestamp.isoformat(), expected_prev,
            ]).encode()
        ).hexdigest()
        if row.prev_hash != expected_prev or row.row_hash != recomputed:
            return False, row.id
        expected_prev = row.row_hash
    return True, None
